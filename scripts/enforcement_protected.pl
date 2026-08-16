use strict;
use warnings;

sub protected_action_digest_impl {
    my ($tool_name, $args) = @_;
    require Digest::SHA;
    json_module();
    my $action = JSON::PP->new->canonical->ascii->encode({
        tool_input => $args, tool_name => lc($tool_name // ''),
    });
    return 'sha256:' . Digest::SHA::sha256_hex($action);
}

sub protected_approval_impl {
    my ($repo, $active, $kind, $tool_name, $args, $session_id, $request_digest) = @_;
    return 0 unless $repo && $active && $kind && $session_id && $request_digest;
    require Cwd;
    my $helper = Cwd::abs_path(__FILE__) // __FILE__;
    my $owner = $helper =~ s{scripts/enforcement_protected\.pl\z}{skills/he/scripts/execution_evidence.py}r;
    my $bounded = $helper =~ s{scripts/enforcement_protected\.pl\z}{skills/deterministic-checks/scripts/bounded_run.py}r;
    my $python = trusted_python();
    return 0 if $owner eq $helper || $bounded eq $helper
        || !defined($python) || !-f $owner || !-f $bounded;
    my $digest = protected_action_digest_impl($tool_name, $args);
    my @command = (
        $python, $bounded, '--timeout', '15', '--cwd', $repo, '--',
        $python, $owner, 'consume-protected', '--repo', $repo,
        '--plan', $active->{path}, '--kind', $kind,
        '--session-id', $session_id, '--request-digest', $request_digest,
        '--tool-name', $tool_name, '--action-digest', $digest,
    );
    local %ENV = %ENV;
    $ENV{PATH} = trusted_command_path();
    my $null_path = $^O eq 'MSWin32' ? 'NUL' : '/dev/null';
    open my $null, '>', $null_path or return 0;
    open my $saved_stdout, '>&', \*STDOUT or return 0;
    open my $saved_stderr, '>&', \*STDERR or return 0;
    my $status;
    open STDOUT, '>&', $null or return 0;
    open STDERR, '>&', $null or return 0;
    system { $command[0] } @command;
    $status = $?;
    open STDOUT, '>&', $saved_stdout or return 0;
    open STDERR, '>&', $saved_stderr or return 0;
    close $null;
    return $status == 0 ? 1 : 0;
}

sub guard_shell_impl {
    my ($command, $repo) = @_;
    return ("Blocked unsupported shell syntax: use one simple command or record exact approval for the indirect action.", 'external-live-write-or-delivery')
        unless shell_syntax_supported_impl($command);
    return ("Blocked suspected secret-bearing shell input. Remove the secret or use the approved secret channel.", 'secret-exposure')
        if has_secret_value_impl($command);
    return ("Hard Eng blocked link creation inside a configured repository. Use a repository-owned no-follow writer.", undef)
        if $repo && $command =~ m{\A(?:\S*/)?ln(?:\s|\z)};
    return ("Blocked $1: ripgrep uses -r for --replace, not recursion. Use rg -n; rg recurses by default.", undef)
        if $command =~ /(?:^|[;&|]\s*|\bsudo\s+|\benv\s+)rg\s+(-[A-Za-z]*r[A-Za-z]+)/;
    return ("Blocked git restore: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?=[^;&|]*(?:--worktree|-[A-Za-z]*W))/
            || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?![^;&|]*--staged(?:\s|$))(?![^;&|]*-[A-Za-z]*S)(?![^;&|]*--source\b)/;
    return ("Blocked git reset: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit\b[^;&|]*\breset\s+--hard\b/
            || $command =~ /\bgit\b[^;&|]*\bcheckout\s+--\b/
            || $command =~ /\bgit\b[^;&|]*\bstash\s+(?:drop|clear)\b/;
    return ("Blocked git clean: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+clean\b(?![^;&|]*(?:-[^\s]*[nN]|--dry-run))/;
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+(reset\s+--hard|checkout\s+--|stash\s+(?:drop|clear))\b/) {
        my $action = $1; $action =~ s/\s.*//;
        return ("Blocked git $action: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema');
    }
    return ("Blocked forced Git push: autonomous mode never rewrites remote history. Get separate exact approval first.", 'force-or-history-rewrite')
        if $command =~ /\bgit\b[^;&|]*\bpush\b[^;&|]*(?:--force(?:-with-lease|-if-includes)?|-f)(?:\s|$)/
            || $command =~ /\bgit\b[^;&|]*\bpush\b[^;&|]*(?:\s|\A)\+[^\s;&|]+/;
    return ("Blocked destructive Git history rewrite: only ordinary local upstream rebases are allowed. Get separate exact approval first.", 'force-or-history-rewrite')
        if $command =~ /\bgit\b[^;&|]*\bfilter-branch\b/
            || ($command =~ /\bgit\b[^;&|]*\brebase\b/
                && ($command =~ /(?:^|\s)(?:-i|--interactive|--root)(?:\s|=|$)/
                    || $command !~ /\bgit(?:\s+-C\s+\S+)?\s+rebase\b[^;&|]*\s[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.\/-]*(?:[~^][^\s;&|]*)?(?=\s|$)/))
            || $command =~ /\bgit\b[^;&|]*\bcommit\b[^;&|]*--amend\b/
            || $command =~ /\bgit\b[^;&|]*\b(?:branch|tag)\b[^;&|]*(?:\s-f\b|--force\b)/;
    return ("Blocked destructive database command: autonomous mode may add data or schema, but deletion requires separate exact approval.", 'data-deletion-or-destructive-schema')
        if $command =~ /\b(?:psql|mysql|sqlite3)\b[^;&|]*\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE(?:\s+TABLE)?|DELETE\s+FROM)\b/i
            || $command =~ /\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE(?:\s+TABLE)?|DELETE\s+FROM)\b[^;&|]*\|\s*(?:psql|mysql|sqlite3)\b/i;
    return ("Blocked git checkout of a file: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+checkout\s+(?!-b\b|-B\b|--branch\b|--orphan\b|--detach\b)(?:\.\.?\/[^;&|\s]+|[^;&|\s]*\.[A-Za-z0-9_-]+)(?:\s|$)/;
    if ($repo && $command =~ /\b(?:rm|unlink|mv|git\s+mv)\b/) {
        my $status = inspect_repo($repo);
        if ($status->{configured} && !$status->{error} && @{$status->{active}}) {
            my $plan = $status->{active}[0]{path};
            my $relative = substr($plan, length($repo) + 1);
            return ("Hard Eng blocked deleting or renaming active $plan.", undef)
                if $command =~ /(?:^|[\s'\"])(?:\.\/)?\Q$relative\E(?:[\s'\"]|$)/
                    || $command =~ /(?:^|[\s'\"])\Q$plan\E(?:[\s'\"]|$)/;
        }
    }
    return (undef, undef);
}

sub has_secret_key_impl {
    my ($value) = @_;
    if (ref($value) eq 'HASH') {
        for my $key (keys %$value) {
            my $compact = lc($key) =~ s/[^a-z0-9]//gr;
            return 1 if $compact =~ /\A(?:apikey|authtoken|authorization|bearer|clientcertificate|clientsecret|connectionstring|cookie|credential|dsn|password|pem|privatekey|secret|session|signedurl|signature|token|accesstoken)\z/;
            return 1 if has_secret_key_impl($value->{$key}) || has_secret_value_impl($value->{$key});
        }
    } elsif (ref($value) eq 'ARRAY') {
        return 1 if grep { has_secret_key_impl($_) || has_secret_value_impl($_) } @$value;
    }
    return 0;
}

sub has_secret_value_impl {
    my ($value) = @_;
    return 0 if ref($value);
    my $text = defined($value) ? "$value" : '';
    return 1 if $text =~ /-----BEGIN [^-]*PRIVATE KEY-----/;
    return 1 if $text =~ /\b(?:Authorization|Cookie|Set-Cookie)\s*[:=]\s*\S+/i;
    return 1 if $text =~ /\bBearer\s+[A-Za-z0-9._~+\/-]{12,}={0,2}\b/i;
    return 1 if $text =~ m{\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp)://[^\s'"<>]+}i;
    return 1 if $text =~ m{\bhttps?://[^\s'"<>]+[?&](?:sig|signature|x-amz-signature|token|access_token)=}i;
    return 0;
}

sub shell_syntax_supported_impl {
    my ($command) = @_;
    return 0 unless defined($command) && $command =~ /\S/;
    my $quote = '';
    my $escaped = 0;
    my @chars = split //, $command;
    for my $char (@chars) {
        if ($escaped) { $escaped = 0; next; }
        if ($quote eq "'") { $quote = '' if $char eq "'"; next; }
        if ($quote eq '"') {
            if ($char eq '"') { $quote = ''; next; }
            return 0 if $char eq '`';
            $escaped = 1 if $char eq '\\';
            next;
        }
        if ($char eq "'" || $char eq '"') { $quote = $char; next; }
        return 0 if $char =~ /[;&|<>()`\r\n]/;
        $escaped = 1 if $char eq '\\';
    }
    return 0 if $quote ne '' || $escaped;
    return 0 if $command =~ /\$\(/;
    my ($first) = split /\s+/, $command;
    return 0 if defined($first) && $first =~ /\$/;
    my $program = $first // '';
    $program =~ s{.*/}{};
    return 0 if $program =~ /\A(?:\.|source|eval|env|exec|sudo|nohup|setsid|timeout|xargs|sh|bash|zsh|fish|dash)\z/;
    return 0 if $first =~ m{/}
        && $first !~ m{(?:\A|/)(?:setup\.sh|publish-gate\.sh|update-managed-skills\.sh)\z}
        && $first !~ m{\A/(?:bin|usr/bin|usr/local/bin|opt/homebrew/bin)/[^/]+\z};
    return 0 if $command =~ m{\A(?:\S*/)?(?:python(?:3)?|node|ruby|php|pwsh|powershell)\b[^;&|]*(?:\s|\A)(?:-c|-e|--eval)(?:\s|=|$)}i
        || $command =~ m{\A(?:\S*/)?perl\b[^;&|]*(?:\s|\A)(?:-e|--eval)(?:\s|=|$)}i;
    return 1;
}

sub external_protected_kind_impl {
    my ($raw_name, $name, $args) = @_;
    return undef unless $raw_name =~ /(?:__|\.)/;
    my $part = qr/(?:\A|_)/; my $end = qr/(?:_|\z)/;
    return 'data-deletion-or-destructive-schema'
        if $name =~ /$part(?:archive|clear|delete|destroy|drop|erase|purge|remove|truncate|wipe)$end/
            || $name =~ /\A(?:archive|clear|delete|destroy|drop|erase|purge|remove|truncate|wipe)/;
    return 'material-payment-or-spend'
        if $name =~ /$part(?:buy|charge|pay|payment|purchase|spend)$end/
            || $name =~ /\A(?:buy|charge|createpayment|makepayment|pay|purchase|spend)/;
    return 'account-or-permission-change'
        if ($name =~ /$part(?:access|account|invite|member|membership|permission|role|user)$end/
            && $name =~ /$part(?:add|change|create|delete|grant|invite|remove|revoke|set|update)$end/)
            || $name =~ /\A(?:add|change|create|delete|grant|invite|remove|revoke|set|update)(?:access|account|invite|member|membership|permission|role|user)/;
    return 'secret-exposure' if has_secret_key_impl($args);
    return undef;
}

sub external_mutating_impl {
    my %mutating = map { $_ => 1 } qw(
        add append apply cancel close commit create deploy disable enable execute
        grant insert invite merge patch publish push refund release remove rename
        revoke send set start stop submit terminate transfer trigger update upload
        upsert write
    );
    return scalar grep { $mutating{$_} } split /_+/, $_[0];
}

sub external_readonly_impl {
    my ($name) = @_;
    return 1 if $name =~ /\Actx_(?:doctor|search|stats)\z/;
    return 0 if external_mutating_impl($name);
    my %readonly = map { $_ => 1 } qw(
        check describe fetch find get inspect list query read search show status view
    );
    my ($first) = split /_+/, $name;
    return defined($first) && $readonly{$first} ? 1 : 0;
}

sub autonomous_external_allowed_impl {
    my ($name) = @_;
    return 1 if $name =~ /(?:\A|_)(?:commit|deploy|merge|publish|push|release)(?:_|\z)/
        || $name =~ /\A(?:commit|deploy|merge|publish|push|release)/
        || $name =~ /(?:pull_request|pullrequest|workflow|ci)(?:_|\z)/;
    return 1 if $name =~ /\A(?:add|append|create|insert)(?:_|-|[a-z])/
        && ($name =~ /(?:\A|_)(?:column|document|field|index|record|row|schema|table)(?:_|\z)/
            || $name =~ /\A(?:add|append|create|insert)(?:column|document|field|index|record|row|schema|table)/);
    return 0;
}

sub authorization_mode_impl {
    my ($active) = @_;
    return undef unless $active;
    my $folder = $active->{path} =~ s{/PLAN\.md\z}{}r;
    my $authorization;
    eval { $authorization = decode_json(slurp("$folder/receipts/authorization.json")); 1 } or return undef;
    return $authorization->{mode}
        if ref($authorization) eq 'HASH'
            && ($authorization->{schema_version} // 0) == 2
            && ($authorization->{mode} // '') =~ /\A(?:standard|autonomous)\z/
            && ($authorization->{expires_at_epoch} // 0) >= time;
    return undef;
}

sub protected_reason_impl {
    my ($kind) = @_;
    return 'Hard Eng blocked this account or permission change. It needs separate exact approval.' if $kind eq 'account-or-permission-change';
    return 'Hard Eng blocked this destructive action. It needs separate exact approval.' if $kind eq 'data-deletion-or-destructive-schema';
    return 'Hard Eng blocked this forced history change. It needs separate exact approval.' if $kind eq 'force-or-history-rewrite';
    return 'Hard Eng blocked this payment or spend. It needs separate exact approval.' if $kind eq 'material-payment-or-spend';
    return 'Hard Eng blocked sending a secret. It needs separate exact approval.' if $kind eq 'secret-exposure';
    return 'Hard Eng blocked this protected action. It needs separate exact approval.';
}

1;
