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
    my ($repo, $active, $kind, $tool_name, $args) = @_;
    return 0 unless $repo && $active && $kind;
    my $folder = $active->{path} =~ s{/PLAN\.md\z}{}r;
    my $path = "$folder/receipts/protected-action.json";
    return 0 unless -f $path && !-l $path;
    my $receipt;
    eval { $receipt = decode_json(slurp($path)); 1 } or return 0;
    return 0 unless ref($receipt) eq 'HASH'
        && ($receipt->{schema_version} // 0) == 1
        && ($receipt->{plan_id} // '') eq ($active->{plan_id} // '')
        && ($receipt->{fingerprint} // '') eq ($active->{approval_fingerprint} // '')
        && ($receipt->{kind} // '') eq $kind
        && ($receipt->{target} // '') ne '' && !ref($receipt->{target})
        && ($receipt->{approval_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
        && ($receipt->{action_digest} // '') eq protected_action_digest_impl($tool_name, $args);
    return unlink($path) ? 1 : 0;
}

sub guard_shell_impl {
    my ($command, $repo) = @_;
    return ("Blocked $1: ripgrep uses -r for --replace, not recursion. Use rg -n; rg recurses by default.", undef)
        if $command =~ /(?:^|[;&|]\s*|\bsudo\s+|\benv\s+)rg\s+(-[A-Za-z]*r[A-Za-z]+)/;
    return ("Blocked git restore: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?=[^;&|]*(?:--worktree|-[A-Za-z]*W))/
            || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?![^;&|]*--staged(?:\s|$))(?![^;&|]*-[A-Za-z]*S)(?![^;&|]*--source\b)/;
    return ("Blocked git clean: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+clean\b(?![^;&|]*(?:-[^\s]*[nN]|--dry-run))/;
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+(reset\s+--hard|checkout\s+--|stash\s+(?:drop|clear))\b/) {
        my $action = $1; $action =~ s/\s.*//;
        return ("Blocked git $action: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.", 'data-deletion-or-destructive-schema');
    }
    return ("Blocked forced Git push: autonomous mode never rewrites remote history. Get separate exact approval first.", 'force-or-history-rewrite')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+push\b[^;&|]*(?:--force(?:-with-lease|-if-includes)?|-f)(?:\s|$)/
            || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+push\b[^;&|]*(?:\s|\A)\+[^\s;&|]+/;
    return ("Blocked destructive Git history rewrite: only ordinary local upstream rebases are allowed. Get separate exact approval first.", 'force-or-history-rewrite')
        if $command =~ /\bgit(?:\s+-C\s+\S+)?\s+filter-branch\b/
            || ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+rebase\b/
                && ($command =~ /(?:^|\s)(?:-i|--interactive|--root)(?:\s|=|$)/
                    || $command !~ /\bgit(?:\s+-C\s+\S+)?\s+rebase\b[^;&|]*\s[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.\/-]*(?:[~^][^\s;&|]*)?(?=\s|$)/))
            || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+commit\b[^;&|]*--amend\b/
            || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+(?:branch|tag)\b[^;&|]*(?:\s-f\b|--force\b)/;
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
            return 1 if $compact =~ /\A(?:apikey|authtoken|clientsecret|password|secret|token|accesstoken)\z/;
            return 1 if has_secret_key_impl($value->{$key});
        }
    } elsif (ref($value) eq 'ARRAY') {
        return 1 if grep { has_secret_key_impl($_) } @$value;
    }
    return 0;
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
    return $_[0] =~ /\A(?:add|append|apply|commit|create|deploy|grant|insert|invite|merge|patch|publish|push|release|remove|revoke|send|set|submit|update|upsert|write)(?:_|-|[a-z])/;
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
        if ref($authorization) eq 'HASH' && ($authorization->{mode} // '') =~ /\A(?:standard|autonomous)\z/;
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
