use strict;
use warnings;

# Discard patterns classify by worktree effect, so every alternative tolerates
# git's global options before the verb and quote characters around flags.
my $GIT_OPTIONS = qr/(?:(?:-[Cc]|--git-dir|--work-tree|--namespace|--exec-path)(?:=\S+|\s+\S+)|-c\S+|--no-pager|--paginate|-p|--bare|--literal-pathspecs|--no-optional-locks|--no-replace-objects|--no-advice)/;
my $GIT_CALL = qr/\bgit(?:\s+$GIT_OPTIONS)*\s+/;

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
    return 0 unless $repo && $kind && $session_id;
    return 0 if $active && !$request_digest;
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
        '--plan', ($active ? $active->{path} : 'direct'), '--kind', $kind,
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
    return ("Blocked suspected secret-bearing shell input. Remove the secret or use the approved secret channel.", 'secret-exposure')
        if has_secret_value_impl($command);
    return ("Blocked git restore: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /${GIT_CALL}restore\b(?=[^;&|]*[\s"'](?:--worktree|-[A-Za-z]*W))/
            || $command =~ /${GIT_CALL}restore\b(?![^;&|]*[\s"']--staged(?:[\s"']|$))(?![^;&|]*[\s"']-[A-Za-z]*S[A-Za-z]*(?:[\s"']|$))/;
    if (
        $command =~ /\bgit\b[^;&|]*\b(reset)\b(?=[^;&|]*\s--hard\b)/
        || $command =~ /\bgit\b[^;&|]*\b(checkout)\b[^;&|]*\s--(?:\s|\z)/
        || $command =~ /\bgit\b[^;&|]*\b(checkout)\s+\.{1,2}\/?(?:\s|;|&|\||\z)/
        || $command =~ /\bgit\b[^;&|]*\b(checkout)\b(?![^;&|]*\s(?:-b|-B|--branch|--orphan|--detach|--track|-t)\b)\s+(?:-[^\s;&|]+\s+)*[^-\s;&|<>][^\s;&|]*\s+(?!\d*[<>])[^-\s;&|<>]/
        || $command =~ /\bgit\b[^;&|]*\b(stash)\s+(?:drop|clear)\b/
    ) {
        my $action = $1;
        return ("Blocked git $action: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema');
    }
    return ("Blocked git clean: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /${GIT_CALL}clean\b(?![^;&|]*(?:-[^\s]*[nN]|--dry-run))/;
    return ("Blocked git reflog deletion: it removes the recovery entries for stashes and old commits. Keep them or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit\b[^;&|]*\breflog\s+(?:delete|expire)\b/;
    return ("Blocked forced Git push: autonomous mode never rewrites remote history. Get separate exact approval first.", 'force-or-history-rewrite')
        if $command =~ /\bgit\b[^;&|]*\bpush\b[^;&|]*[\s"'](?:--force(?:-with-lease|-if-includes)?|-[A-Za-z]*f[A-Za-z]*)(?:[="'\s]|$)/
            || $command =~ /\bgit\b[^;&|]*\bpush\b[^;&|]*(?:\s|\A)\+[^\s;&|]+/;
    return ("Blocked destructive database command: autonomous mode may add data or schema, but deletion requires separate exact approval.", 'data-deletion-or-destructive-schema')
        if $command =~ /\b(?:psql|mysql|mariadb|sqlite3)\b[^;&|]*\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE(?:\s+TABLE)?|DELETE\s+FROM)\b/i
            || $command =~ /\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE(?:\s+TABLE)?|DELETE\s+FROM)\b[^;&|]*\|\s*(?:psql|mysql|mariadb|sqlite3)\b/i;
    return ("Blocked permanent Wrangler deletion. It needs separate exact approval.", 'data-deletion-or-destructive-schema')
        if $command =~ /(?:\A|[;&|]\s*)(?:\S*\/)?(?:npx\s+(?:--yes\s+)?wrangler(?:@\S+)?|wrangler)\b[^;&|]*\bdelete\b/i;
    return ("Blocked git checkout of a file: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /${GIT_CALL}checkout\s+(?!-b\b|-B\b|--branch\b|--orphan\b|--detach\b)(?:\.\.?\/[^;&|\s]+|[^;&|\s]*\.[A-Za-z0-9_-]+)(?:\s|$)/;
    # The file-tool guard cannot see shell. These are the writers that reach a
    # machine-wide destination often enough to be worth naming; shell coverage is
    # a bounded list, never a parser, so it narrows the hole without closing it.
    while ($command =~ /(?:\A|[;&|]\s*)(?:\S*\/)?git\s+(?:$GIT_OPTIONS\s+)*config\b([^;&|]*)/g) {
        my $segment = $1;
        next unless $segment =~ /\s(?:--global|--system)\b/
            || $segment =~ /\s--file[=\s]+["']?(?:~|\$HOME|\$\{HOME\})/;
        my $read = $segment =~ /\s(?:--get(?:-all|-regexp|-urlmatch|-color(?:bool)?)?|--list|-l)(?:\s|\z)/
            || $segment =~ /\A\s+(?:(?:--global|--system)\s+)?(?:get|list)(?:\s|\z)/;
        my $write = $segment =~ /\s(?:--add|--unset(?:-all)?|--replace-all|--edit|-e|--rename-section|--remove-section)(?:\s|\z)/
            || $segment =~ /\A\s+(?:(?:--global|--system)\s+)?(?:set|unset|edit|rename-section|remove-section)(?:\s|\z)/;
        return ("Blocked a machine-wide settings write. It changes every other repository on this machine, so name the exact file and effect to the user and get their plain yes first.", 'machine-scope-write')
            if !$read || $write;
    }
    return ("Blocked a machine-wide settings write. It changes every other repository on this machine, so name the exact file and effect to the user and get their plain yes first.", 'machine-scope-write')
        if $command =~ /(?:\A|[;&|]\s*)(?:\S*\/)?(?:codex|claude)\s+mcp\s+add\b/
            || $command =~ /(?:\A|[;&|]\s*)(?:\S*\/)?(?:(?:npm|pnpm|yarn|gh)\s+config\s+set\b|npm\s+set(?![\w-]))(?![^;&|]*--location[=\s]project)/
            || $command =~ /(?:\A|[;&|]\s*)(?:\S*\/)?defaults\s+(?:-currentHost\s+)?write\b/;
    return ("Blocked writing to a file in the home directory. It changes every other repository on this machine, so name the exact file and effect to the user and get their plain yes first.", 'machine-scope-write')
        if $command =~ /(?:>>?|\btee\b(?:\s+(?:-a|--append))?\s+)\s*(?:"|')?(?:~|\$HOME|\$\{HOME\})\/\S/;

    if ($command =~ /\b(?:rm|unlink)\b/) {
        if ($repo) {
            my $status = inspect_repo($repo);
            if ($status->{configured} && !$status->{error} && @{$status->{active}}) {
                my $plan = $status->{active}[0]{path};
                my $relative = substr($plan, length($repo) + 1);
                return ("Hard Eng blocked permanently deleting active $plan.", 'data-deletion-or-destructive-schema')
                    if $command =~ /(?:^|[\s'\"])(?:\.\/)?\Q$relative\E(?:[\s'\"]|$)/
                        || $command =~ /(?:^|[\s'\"])\Q$plan\E(?:[\s'\"]|$)/;
            }
        }
        # The session cwd may sit in a different repository than the rm target,
        # so an absolute PLAN.md path resolves its own repository.
        while ($command =~ m{((?:/[^/\s'";&|]+)+/features/[^/\s'";&|]+/PLAN\.md)}g) {
            my $plan_path = $1;
            my $candidate = $plan_path;
            $candidate =~ s{/features/[^/]+/PLAN\.md\z}{};
            next if $repo && $candidate eq $repo;
            next unless -f $plan_path && -d $candidate;
            my $status = inspect_repo($candidate);
            next unless $status->{configured} && !$status->{error};
            for my $active (@{$status->{active}}) {
                return ("Hard Eng blocked permanently deleting active $plan_path.", 'data-deletion-or-destructive-schema')
                    if $active->{path} eq $plan_path;
            }
        }
    }
    return (undef, undef);
}

sub has_secret_key_impl {
    my ($value) = @_;
    if (ref($value) eq 'HASH') {
        for my $key (keys %$value) {
            my $compact = lc($key) =~ s/[^a-z0-9]//gr;
            return 1 if $compact =~ /\A(?:apikey|apitoken|authtoken|authorization|bearer|clientcertificate|clientsecret|connectionstring|cookie|credential|dsn|password|pem|privatekey|secret|session|signedurl|signature|token|accesstoken)\z/;
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

sub external_protected_kind_impl {
    my ($raw_name, $name, $args) = @_;
    return undef unless $raw_name =~ /(?:__|\.)/;
    my $part = qr/(?:\A|_)/; my $end = qr/(?:_|\z)/;
    return 'data-deletion-or-destructive-schema'
        if $name =~ /$part(?:delete|destroy|drop|erase|purge|truncate|wipe)$end/
            || $name =~ /\A(?:delete|destroy|drop|erase|purge|truncate|wipe)/;
    return 'secret-exposure' if has_secret_key_impl($args);
    return undef;
}

sub protected_reason_impl {
    my ($kind) = @_;
    return 'Hard Eng blocked this permanent destructive action. It needs separate exact approval.' if $kind eq 'data-deletion-or-destructive-schema';
    return 'Hard Eng blocked this forced remote history change. It needs separate exact approval.' if $kind eq 'force-or-history-rewrite';
    return 'Hard Eng blocked irreversible secret exposure. It needs separate exact approval.' if $kind eq 'secret-exposure';
    return 'Hard Eng blocked a change to settings outside this repository. Name the exact file and its machine-wide effect to the user and get their plain yes first.' if $kind eq 'machine-scope-write';
    return 'Hard Eng blocked this irreversible destructive action. It needs separate exact approval.';
}

1;
