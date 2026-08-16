#!/usr/bin/env perl
use strict;
use warnings;

sub json_module {
    require JSON::PP;
    return 'JSON::PP';
}

sub encode_json {
    json_module();
    return JSON::PP->new->canonical->encode($_[0]);
}

sub decode_json {
    json_module();
    return JSON::PP->new->decode($_[0]);
}

sub slurp {
    my ($path) = @_;
    my $current = '';
    for my $part (split m{/}, normalise($path)) {
        next if $part eq '';
        $current .= "/$part";
        die "$path contains a symlink" if -l $current;
    }
    require Fcntl;
    my $flags = Fcntl::O_RDONLY();
    $flags |= Fcntl::O_NOFOLLOW() if defined &Fcntl::O_NOFOLLOW;
    sysopen my $handle, $path, $flags or die "$path: $!";
    die "$path is not a regular file" unless -f $handle;
    local $/;
    return <$handle>;
}

sub trusted_python {
    require Cwd;
    for my $candidate (
        '/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3'
    ) {
        next unless -x $candidate;
        my $resolved = Cwd::abs_path($candidate);
        return $resolved if defined($resolved) && -f $resolved && -x $resolved;
    }
    return undef;
}

sub trusted_command_path {
    return '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin';
}

sub absolute_path {
    my ($base, $path) = @_;
    my $lexical = normalise($path =~ m{^/} ? $path : "$base/$path");
    my $current = '';
    for my $part (split m{/}, $lexical) {
        next if $part eq '';
        $current .= "/$part";
        next unless -l $current;
        require Cwd;
        my $resolved = Cwd::abs_path($lexical);
        return normalise($resolved) if defined $resolved;
        my ($parent, $name) = $lexical =~ m{\A(.+)/([^/]+)\z};
        my $real_parent = defined $parent ? Cwd::abs_path($parent) : undef;
        return normalise("$real_parent/$name") if defined $real_parent;
    }
    return $lexical;
}

sub normalise {
    my ($path) = @_;
    my @parts;
    for my $part (split m{/+}, $path) {
        next if $part eq '' || $part eq '.';
        if ($part eq '..') {
            pop @parts;
        } else {
            push @parts, $part;
        }
    }
    return '/' . join('/', @parts);
}

sub lexical_target_path {
    my ($base, $value) = @_;
    return undef unless defined($value) && !ref($value) && $value ne '';
    return undef if grep { $_ eq '..' } split m{/}, $value;
    my $lexical = normalise($value =~ m{^/} ? $value : "$base/$value");
    my $current = '';
    for my $part (split m{/}, $lexical) {
        next if $part eq '';
        $current .= "/$part";
        return undef if -l $current;
    }
    return $lexical;
}

sub repo_root {
    my ($start) = @_;
    my $path = normalise($start =~ m{^/} ? $start : "$ENV{PWD}/$start");
    $path =~ s{/[^/]+$}{} unless -d $path;
    while ($path ne '') {
        return $path if -e "$path/.git";
        last if $path eq '/';
        $path =~ s{/[^/]+$}{};
        $path = '/' if $path eq '';
    }
    return undef;
}

sub manifest_status {
    my ($repo) = @_;
    my $path = "$repo/hard-eng.gates.json";
    return (0, undef) unless -e $path || -l $path;
    return (1, 'hard-eng.gates.json must be a regular non-symlink file')
        if -l $path || !-f $path;
    my $data;
    eval { $data = decode_json(slurp($path)); 1 }
        or return (1, "hard-eng.gates.json is invalid");
    return (0, undef) unless ref($data) eq 'HASH' && exists $data->{enforcement};
    my $config = $data->{enforcement};
    return (1, 'hard-eng.gates.json enforcement requires schema_version 1')
        unless ref($config) eq 'HASH' && ($config->{schema_version} // 0) == 1;
    return (1, undef);
}

my $CHECKPOINT_HELPER = __FILE__ =~ s{[^/]+\z}{enforcement_checkpoint.pl}r;
$CHECKPOINT_HELPER = "./$CHECKPOINT_HELPER" unless $CHECKPOINT_HELPER =~ m{\A(?:/|\./|\.\./)};

sub load_checkpoint_helper { require $CHECKPOINT_HELPER; }
sub coverage_status { load_checkpoint_helper(); return coverage_status_impl(@_); }

sub markdown_files {
    my ($folder, $plan) = @_;
    my @found;
    my @pending = ($folder);
    while (my $directory = shift @pending) {
        opendir my $handle, $directory or return ("cannot read $directory");
        for my $name (sort grep { $_ ne '.' && $_ ne '..' } readdir $handle) {
            my $path = "$directory/$name";
            push @pending, $path if -d $path && !-l $path;
            push @found, $path if -f $path && $path =~ /\.md\z/ && $path ne $plan;
        }
        closedir $handle;
    }
    return @found;
}

sub execution_evidence_error {
    my ($repo, $plan, $text) = @_;
    return 'active Feature Brief is missing plan_id'
        unless $text =~ /^- plan_id = (\S+)$/m;
    my $plan_id = $1;
    return 'active Feature Brief is missing approved fingerprint'
        unless $text =~ /^- approval_fingerprint = (sha256:[0-9a-f]{64})$/m;
    my $fingerprint = $1;
    my $folder = $plan =~ s{/PLAN\.md\z}{}r;
    my ($research, $authorization);
    eval {
        $research = decode_json(slurp("$folder/receipts/research.json"));
        $authorization = decode_json(slurp("$folder/receipts/authorization.json"));
        1;
    } or return 'approved Feature Brief requires valid research.json and authorization.json receipts';
    my @today_parts = localtime;
    my $today = sprintf('%04d-%02d-%02d', $today_parts[5] + 1900, $today_parts[4] + 1, $today_parts[3]);
    return 'research receipt does not match the active Feature Brief'
        unless ref($research) eq 'HASH'
            && ($research->{schema_version} // 0) == 1
            && ($research->{plan_id} // '') eq $plan_id
            && ($research->{scope} // '') =~ /\A(?:local|external)\z/
            && ref($research->{sources}) eq 'ARRAY' && @{$research->{sources}}
            && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$research->{sources}})
            && ref($research->{source_versions}) eq 'ARRAY'
            && @{$research->{source_versions}} == @{$research->{sources}}
            && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$research->{source_versions}})
            && ref($research->{verified}) eq 'ARRAY' && @{$research->{verified}}
            && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$research->{verified}})
            && ref($research->{unknown}) eq 'ARRAY'
            && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$research->{unknown}})
            && ($research->{question} // '') ne '' && !ref($research->{question})
            && ($research->{decision} // '') ne '' && !ref($research->{decision})
            && ($research->{repository_head} // '') ne '' && !ref($research->{repository_head})
            && ($research->{checked_at} // '') =~ /\A\d{4}-\d{2}-\d{2}\z/
            && ($research->{fresh_until} // '') =~ /\A\d{4}-\d{2}-\d{2}\z/
            && $research->{checked_at} le $today && $today le $research->{fresh_until};
    if ($research->{scope} eq 'external') {
        return 'external research receipt requires HTTPS primary sources'
            if grep { !defined($_) || ref($_) || $_ !~ m{\Ahttps://} } @{$research->{sources}};
    } else {
        for my $source (@{$research->{sources}}) {
            return 'local research receipt has an invalid source'
                if !defined($source) || ref($source) || $source =~ m{\A/|(?:\A|/)\.\.(?:/|\z)}
                    || !-f "$repo/$source" || -l "$repo/$source";
        }
    }
    my @stops = qw(
        account-or-permission-change data-deletion-or-destructive-schema
        force-or-history-rewrite material-payment-or-spend
        protected-live-write-retry secret-exposure
    );
    my $allowed_ok = ref($authorization->{allowed}) eq 'ARRAY'
        && @{$authorization->{allowed}}
        && !(grep {
            !defined($_) || ref($_) || $_ !~ /\A[a-z0-9][a-z0-9._:\/\@+\-]{1,159}\z/
        } @{$authorization->{allowed}})
        && (($authorization->{mode} // '') eq 'autonomous'
            || join("\0", @{$authorization->{allowed}}) eq 'approved-build'
            || join("\0", @{$authorization->{allowed}}) eq "approved-build\0parallel-subagents");
    return 'authorization receipt does not match the approved Feature Brief'
        unless ref($authorization) eq 'HASH'
            && ($authorization->{schema_version} // 0) == 2
            && ($authorization->{plan_id} // '') eq $plan_id
            && ($authorization->{plan_fingerprint} // '') eq $fingerprint
            && ($authorization->{mode} // '') =~ /\A(?:standard|autonomous)\z/
            && ($authorization->{approval_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && ($authorization->{session_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && ($authorization->{request_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && ($authorization->{expires_at_epoch} // 0) >= time
            && ref($authorization->{repository_context}) eq 'HASH'
            && $allowed_ok
            && ref($authorization->{stop_before}) eq 'ARRAY'
            && join("\0", @{$authorization->{stop_before}}) eq join("\0", @stops);
    return undef;
}

sub plan_status {
    my ($repo) = @_;
    my $features = "$repo/features";
    return ([], undef) unless -d $features;
    opendir my $handle, $features or return ([], "cannot read features");
    my @folders = sort grep { $_ ne '.' && $_ ne '..' && -d "$features/$_" } readdir $handle;
    closedir $handle;
    my @active;
    for my $folder (@folders) {
        return ([], "active feature folder must not be a symlink: features/$folder")
            if -l "$features/$folder";
        my $plan = "$features/$folder/PLAN.md";
        next unless -e $plan || -l $plan;
        return ([], "active plan must be a regular file: features/$folder/PLAN.md")
            if -l $plan || !-f $plan;
        my $text;
        eval { $text = slurp($plan); 1 }
            or return ([], "cannot read features/$folder/PLAN.md");
        return ([], "cannot read lifecycle state from features/$folder/PLAN.md")
            unless $text =~ /^- lifecycle_status = ([a-z-]+)$/m;
        my $state = $1;
        return ([], "unknown lifecycle state in features/$folder/PLAN.md: $state")
            unless $state =~ /\A(?:planning|build-ready|building|green|shipped|cancelled)\z/;
        next unless $state =~ /\A(?:planning|build-ready|building|green)\z/;
        if ($state ne 'planning') {
            return ([], "active Feature Brief is missing approved preflight: features/$folder/PLAN.md")
                unless $text =~ /^- approval_status = approved$/m
                    && $text =~ /^- approval_fingerprint = sha256:[0-9a-f]{64}$/m;
            if (my $evidence_error = execution_evidence_error($repo, $plan, $text)) {
                return ([], "$evidence_error: features/$folder/PLAN.md");
            }
        }
        my @extra = markdown_files("$features/$folder", $plan);
        return ([], "active feature has extra Markdown file: " . normalise($extra[0])) if @extra;
        return ([], "active Feature Brief is missing plan_id: features/$folder/PLAN.md")
            unless $text =~ /^- plan_id = (\S+)$/m;
        my $plan_id = $1;
        my ($approval_fingerprint) = $text =~ /^- approval_fingerprint = (sha256:[0-9a-f]{64})$/m;
        push @active, {
            approval_fingerprint => $approval_fingerprint // '',
            path => normalise($plan), plan_id => $plan_id, state => $state,
        };
    }
    if (@active > 1) {
        return (\@active, 'multiple active Feature Briefs: ' . join(', ', map { $_->{path} } @active));
    }
    return (\@active, undef);
}

sub inspect_repo {
    my ($repo) = @_;
    my ($configured, $error) = manifest_status($repo);
    return { configured => 0 } unless $configured;
    return { configured => 1, error => $error } if $error;
    my ($active, $plan_error) = plan_status($repo);
    return { configured => 1, error => $plan_error, active => $active };
}

sub changed_source_error { load_checkpoint_helper(); return changed_source_error_impl(@_); }
sub learning_status_error { load_checkpoint_helper(); return learning_status_error_impl(@_); }

sub lifecycle_target_allowed {
    my ($repo, $active, $target) = @_;
    return 0 unless $active && defined($target) && $target =~ m{\A\Q$repo\E/(.+)\z};
    my $relative = $1;
    my $plan = $active->{path};
    my $feature = $plan =~ m{\A\Q$repo\E/features/([a-z0-9]+(?:-[a-z0-9]+)*)/PLAN\.md\z}
        ? $1 : undef;
    return 0 unless $feature;
    return 1 if $relative eq 'hard-eng.gates.json';
    return 1 if $relative eq "features/$feature/PLAN.md";
    return 1 if $relative =~ m{\Afeatures/\Q$feature\E/receipts/[a-z0-9][a-z0-9._-]*\.json\z};
    return 1 if $relative =~ m{\A\.agents/learning/[a-z0-9]+(?:-[a-z0-9]+)*\.json\z};
    return 0;
}

sub lifecycle_state_owned_target {
    my ($active, $target) = @_;
    return 0 unless $active && defined($target);
    return 1 if $target eq $active->{path};
    my $folder = $active->{path} =~ s{/PLAN\.md\z}{}r;
    return index($target, "$folder/receipts/") == 0 ? 1 : 0;
}

sub active_execution_valid {
    my ($repo, $active, $session_id, $request_digest) = @_;
    if (!defined($request_digest) || $request_digest eq '') {
        my $folder = $active->{path} =~ s{/PLAN\.md\z}{}r;
        my $authorization;
        eval {
            $authorization = decode_json(
                slurp("$folder/receipts/authorization.json")
            );
            1;
        } or return 0;
        $request_digest = $authorization->{request_digest} // ''
            if ref($authorization) eq 'HASH';
    }
    load_direct_helper();
    my ($valid) = direct_owner_impl(
        $repo, 'check', '--repo', $repo,
        '--plan', $active->{path},
        '--fingerprint', $active->{approval_fingerprint},
        '--session-id', $session_id,
        '--request-digest', $request_digest,
        '--allow-repository-drift',
    );
    return $valid;
}

sub write_decision {
    my ($repo, $targets, $deletes, $session_id, $request_digest) = @_;
    my $status = inspect_repo($repo);
    return undef unless $status->{configured};
    return "Hard Eng blocked this write: $status->{error}. Run ./setup.sh check." if $status->{error};
    return 'Hard Eng blocked this write because the adapter did not provide a target path. Run ./setup.sh check.'
        unless @$targets;
    my $active = @{$status->{active}} ? $status->{active}[0] : undef;
    my ($direct, $direct_error);
    ($direct, $direct_error) = direct_route($repo, $session_id, $request_digest) unless $active;
    return 'Hard Eng blocked this write because the active authorization does not match the current session, request, checkout, or HEAD.'
        if $active && $active->{state} ne 'planning' && !active_execution_valid(
            $repo, $active, $session_id // '', $request_digest // ''
        );
    my $direct_write = 0;
    for my $target (@$targets) {
        return 'Hard Eng blocked this write because its target is outside the current repository.'
            unless $target eq $repo || index($target, "$repo/") == 0;
        return 'Hard Eng blocked this raw write to lifecycle-owned PLAN.md or receipt state. Use the lifecycle command owner.'
            if lifecycle_state_owned_target($active, $target);
        my $relative = substr($target, length($repo) + 1);
        my $new_plan = $relative =~ m{\Afeatures/[^/]+/PLAN\.md\z} && !-e $target;
        if (!$active && !$new_plan) {
            return "Hard Eng blocked this direct write: $direct_error. Start the direct route for this task."
                unless $direct;
            return "Hard Eng blocked this direct write outside its intended paths: $relative."
                unless direct_allows_target($repo, $direct, $target);
            $direct_write = 1;
        }
        if ($active && $target eq $active->{path} && $deletes->{$target}) {
            return "Hard Eng blocked deleting or renaming active $active->{path}.";
        }
        if ($active && $target =~ /\.md\z/i && index($target, $active->{path} =~ s{/PLAN\.md\z}{}r . '/') == 0 && $target ne $active->{path}) {
            return "Hard Eng blocked an extra Markdown file in the active feature: $target.";
        }
        if ($active && $active->{state} ne 'building') {
            return "Hard Eng blocked this product write while the Feature Brief is $active->{state}. Move it to building first."
                unless lifecycle_target_allowed($repo, $active, $target);
        }
    }
    return 'Hard Eng blocked this direct write because its one-use route nonce was already consumed.'
        if $direct_write
            && !consume_direct_route(
                $repo, $direct, $session_id, $request_digest
            );
    return undef;
}

sub deny {
    my ($runtime, $reason) = @_;
    my $body = $runtime eq 'copilot'
        ? { permissionDecision => 'deny', permissionDecisionReason => $reason }
        : { hookSpecificOutput => {
            hookEventName => 'PreToolUse', permissionDecision => 'deny',
            permissionDecisionReason => $reason,
        } };
    print encode_json($body);
    return 0;
}

my $DIRECT_HELPER = __FILE__ =~ s{[^/]+\z}{enforcement_direct.pl}r;
$DIRECT_HELPER = "./$DIRECT_HELPER" unless $DIRECT_HELPER =~ m{\A(?:/|\./|\.\./)};

sub load_direct_helper {
    require $DIRECT_HELPER;
}

sub direct_route {
    load_direct_helper();
    return direct_route_impl(@_);
}

sub direct_allows_target {
    load_direct_helper();
    return direct_allows_target_impl(@_);
}

sub consume_direct_route {
    load_direct_helper();
    return consume_direct_route_impl(@_);
}

my $PROTECTED_HELPER = __FILE__ =~ s{[^/]+\z}{enforcement_protected.pl}r;
$PROTECTED_HELPER = "./$PROTECTED_HELPER" unless $PROTECTED_HELPER =~ m{\A(?:/|\./|\.\./)};

sub load_protected_helper { require $PROTECTED_HELPER; }
sub protected_approval { load_protected_helper(); return protected_approval_impl(@_); }
sub guard_shell { load_protected_helper(); return guard_shell_impl(@_); }
sub external_protected_kind { load_protected_helper(); return external_protected_kind_impl(@_); }
sub external_mutating { load_protected_helper(); return external_mutating_impl(@_); }
sub external_readonly { load_protected_helper(); return external_readonly_impl(@_); }
sub autonomous_external_allowed { load_protected_helper(); return autonomous_external_allowed_impl(@_); }
sub authorization_mode { load_protected_helper(); return authorization_mode_impl(@_); }
sub protected_reason { load_protected_helper(); return protected_reason_impl(@_); }

sub scalar_strings {
    my ($value) = @_;
    return ($value) unless ref($value);
    return map { scalar_strings($_) } @$value if ref($value) eq 'ARRAY';
    return map { scalar_strings($_) } values %$value if ref($value) eq 'HASH';
    return ();
}

sub subagent_allowed {
    my ($active) = @_;
    return 0 unless $active;
    my $folder = $active->{path} =~ s{/PLAN\.md\z}{}r;
    my $authorization;
    eval { $authorization = decode_json(slurp("$folder/receipts/authorization.json")); 1 }
        or return 0;
    return 0 unless ref($authorization) eq 'HASH' && ref($authorization->{allowed}) eq 'ARRAY';
    return scalar grep { defined($_) && !ref($_) && $_ eq 'parallel-subagents' } @{$authorization->{allowed}};
}

sub direct_subagent_allowed {
    my ($repo, $session_id, $request_digest) = @_;
    my ($receipt) = direct_route($repo, $session_id, $request_digest);
    return 0 unless $receipt && ref($receipt->{allowed}) eq 'ARRAY';
    return scalar grep { defined($_) && !ref($_) && $_ eq 'parallel-subagents' }
        @{$receipt->{allowed}};
}

sub learning_subagent_allowed {
    my ($repo, $item, $payload) = @_;
    my $args = $item->{args} // $item->{toolArgs} // $payload->{tool_input}
        // $payload->{toolArgs} // $payload->{tool_args} // $payload->{arguments};
    my $joined = join "\n", scalar_strings($args);
    return 0 unless $joined =~ /\bhe-learn\b/i;
    return 0 unless $joined =~ m{(?:\A|\s)(\.agents/learning/([a-z0-9]+(?:-[a-z0-9]+)*)\.json)(?:\s|\z)}i;
    my ($relative, $learning_id) = ($1, lc $2);
    my $path = "$repo/$relative";
    return 0 unless -f $path && !-l $path;
    return 0 if learning_status_error($repo, 0);
    require Fcntl;
    open my $handle, '+<', $path or return 0;
    flock($handle, Fcntl::LOCK_EX()) or do { close $handle; return 0 };
    local $/;
    my $raw = <$handle> // '';
    my $record;
    eval { $record = decode_json($raw); 1 } or do { close $handle; return 0 };
    my $allowed = ref($record) eq 'HASH'
        && ($record->{schema_version} // 0) == 1
        && ($record->{learning_id} // '') eq $learning_id
        && ($record->{status} // '') eq 'open'
        && ref($record->{helper}) eq 'HASH'
        && ($record->{helper}{name} // '') eq 'he-learn'
        && ($record->{helper}{selections} // 0) == 1
        && ($record->{helper}{state} // '') eq 'selected'
        && !ref($record->{next_action})
        && ($record->{next_action} // '') ne ''
        && ($record->{next_action} // '') ne 'none';
    if ($allowed) {
        $record->{helper}{state} = 'launched';
        seek($handle, 0, 0) or $allowed = 0;
        truncate($handle, 0) or $allowed = 0;
        print {$handle} encode_json($record), "\n" or $allowed = 0 if $allowed;
    }
    close $handle;
    return $allowed;
}

sub hook_main {
    my ($runtime, $event) = @_;
    return 0 unless lc($event // '') eq 'pretooluse';
    local $/;
    my $raw = <STDIN> // '';
    my $payload;
    eval { $payload = decode_json($raw); 1 } or return 0;
    return 0 unless ref($payload) eq 'HASH';
    my @items = ref($payload->{toolCalls}) eq 'ARRAY' ? @{$payload->{toolCalls}} : ($payload);
    for my $item (@items) {
        next unless ref($item) eq 'HASH';
        my $original_name = $item->{name} // $item->{toolName}
            // $payload->{tool_name} // $payload->{toolName} // '';
        my $raw_name = lc($original_name);
        my $name = $original_name;
        $name =~ s/^.*(?:__|\.)//;
        $name =~ s/([a-z0-9])([A-Z])/$1_$2/g;
        $name = lc($name);
        $name =~ s/[^a-z0-9]+/_/g;
        $name =~ s/\A_+|_+\z//g;
        if ($name =~ /\A(?:agent|task|spawn_agent|create_agent)\z/) {
            my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
            my $repo = repo_root($cwd);
            next unless $repo && -f "$repo/hard-eng.gates.json";
            my $status = inspect_repo($repo);
            next unless $status->{configured};
            return deny($runtime, "Hard Eng blocked this subagent: $status->{error}.")
                if $status->{error};
            my $active = @{$status->{active}} ? $status->{active}[0] : undef;
            return deny($runtime, 'Hard Eng blocked this subagent because the active authorization does not match the current session, request, checkout, or HEAD.')
                if $active && $active->{state} ne 'planning' && !active_execution_valid(
                    $repo, $active,
                    $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
            return deny($runtime, "Hard Eng blocked this subagent because the current prompt did not explicitly authorize parallel agents.")
                unless learning_subagent_allowed($repo, $item, $payload)
                    || ($active ? subagent_allowed($active) : direct_subagent_allowed(
                    $repo, $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // ''
                    ));
            next;
        }
        my $args = $item->{args} // $item->{toolArgs} // $payload->{tool_input} // $payload->{toolArgs} // $payload->{tool_args} // $payload->{arguments};
        my $malformed = 0;
        if (!ref($args) && defined $args) {
            my $decoded;
            if ($name eq 'apply_patch' && $args =~ /^\*\*\* Begin Patch/m) {
                $args = { patch => $args };
            } else {
                eval { $decoded = decode_json($args); 1 } or $malformed = 1;
                $args = $decoded if ref($decoded) eq 'HASH';
            }
        }
        $args = {} unless ref($args) eq 'HASH';
        if ($name =~ /\A(?:bash|exec_command|shell|run_command|terminal)\z/) {
            my $command = $args->{command} // $args->{cmd} // '';
            $command = '' if ref($command);
            my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
            my $repo = repo_root($cwd);
            my ($reason, $kind) = guard_shell($command, $repo);
            if ($reason) {
                my $active;
                if ($repo && -f "$repo/hard-eng.gates.json") {
                    my $status = inspect_repo($repo);
                    $active = $status->{active}[0]
                        if $status->{configured} && !$status->{error} && @{$status->{active}};
                }
                next if $kind && protected_approval(
                    $repo, $active, $kind, $raw_name, $args,
                    $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
                return deny($runtime, $reason);
            }
            next;
        }
        my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
        my $repo = repo_root($cwd);
        if ($raw_name =~ /(?:__|\.)/ && $repo && -f "$repo/hard-eng.gates.json") {
            my $status = inspect_repo($repo);
            return deny($runtime, "Hard Eng blocked this external action: $status->{error}.")
                if $status->{configured} && $status->{error};
            my $active = $status->{configured} && @{$status->{active}}
                ? $status->{active}[0] : undef;
            if ($active && (my $kind = external_protected_kind($raw_name, $name, $args))) {
                next if protected_approval(
                    $repo, $active, $kind, $raw_name, $args,
                    $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
                return deny($runtime, protected_reason($kind));
            }
            if (!external_readonly($name) && !external_mutating($name)) {
                my $kind = 'external-live-write-or-delivery';
                if ($active) {
                    next if protected_approval(
                        $repo, $active, $kind, $raw_name, $args,
                        $payload->{session_id} // $payload->{sessionId} // '',
                        $payload->{request_digest} // $payload->{requestDigest} // '',
                    );
                }
                return deny($runtime, 'Hard Eng blocked this unknown external action. It needs exact approval.');
            }
            if ($active && external_mutating($name)) {
                return deny($runtime, 'Hard Eng blocked this external write because the active authorization does not match the current session, request, checkout, or HEAD.')
                    unless active_execution_valid(
                        $repo, $active,
                        $payload->{session_id} // $payload->{sessionId} // '',
                        $payload->{request_digest} // $payload->{requestDigest} // '',
                    );
                my $mode = authorization_mode($active) // 'standard';
                next if $mode eq 'autonomous' && autonomous_external_allowed($name);
                my $kind = 'external-live-write-or-delivery';
                next if protected_approval(
                    $repo, $active, $kind, $raw_name, $args,
                    $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
                return deny($runtime, 'Hard Eng blocked this live write or delivery action. It needs separate exact approval.');
            }
            if (!$active && external_mutating($name)) {
                my $session_id = $payload->{session_id} // $payload->{sessionId} // '';
                my ($direct) = direct_route(
                    $repo, $session_id,
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
                return deny($runtime, $direct
                    ? 'Hard Eng blocked this live write or delivery action. Start a Feature Loop so its target and approval can be recorded.'
                    : 'Hard Eng blocked this external write because this task has no valid route receipt.');
            }
        }
        next unless $name =~ /\A(?:apply_patch|create|create_file|edit|edit_file|multiedit|notebookedit|str_replace|str_replace_editor|write|write_file)\z/;
        next unless $repo && -f "$repo/hard-eng.gates.json";
        $repo = absolute_path('/', $repo);
        my (@targets, %deletes);
        my $unsafe_target = 0;
        my $target_base = absolute_path('/', $cwd);
        for my $key (qw(file_path filePath path file notebook_path notebookPath)) {
            next unless defined $args->{$key} && !ref($args->{$key});
            my $target = lexical_target_path($target_base, $args->{$key});
            unless (defined $target) {
                $unsafe_target = 1;
                next;
            }
            push @targets, $target;
        }
        for my $body (scalar_strings($args)) {
            next unless defined $body;
            while ($body =~ /^\*\*\* (Add|Update|Delete) File: (.+)$/mg) {
                my $target = lexical_target_path($target_base, $2);
                unless (defined $target) {
                    $unsafe_target = 1;
                    next;
                }
                push @targets, $target;
                $deletes{$target} = 1 if $1 eq 'Delete';
            }
        }
        return deny($runtime, 'Hard Eng blocked this write because its path contains a symlink or invalid component. Active PLAN.md aliases are not writable.')
            if $unsafe_target;
        @targets = () if $malformed;
        my %seen;
        @targets = grep { !$seen{$_}++ } @targets;
        my $session_id = $payload->{session_id} // $payload->{sessionId} // '';
        my $reason = write_decision(
            $repo, \@targets, \%deletes, $session_id,
            $payload->{request_digest} // $payload->{requestDigest} // '',
        );
        return deny($runtime, $reason) if $reason;
    }
    return 0;
}

if (($ARGV[0] // '') eq 'check') {
    require Cwd;
    my $repo = absolute_path(Cwd::getcwd(), $ARGV[1] // '.');
    my $status = inspect_repo($repo);
    if (!$status->{configured}) {
        warn "Hard Eng enforcement is not configured: $repo\n";
        exit 4;
    }
    if ($status->{error}) {
        warn "Hard Eng enforcement check failed: $status->{error}\n";
        exit 4;
    }
    my ($coverage, $coverage_error) = coverage_status($repo);
    if ($coverage_error) {
        warn "Hard Eng enforcement check failed: $coverage_error\n";
        exit 4;
    }
    my $active = @{$status->{active}} ? $status->{active}[0] : undef;
    if (my $change_error = changed_source_error($repo, $active)) {
        warn "Hard Eng enforcement check failed: $change_error\n";
        exit 4;
    }
    if (my $learning_error = learning_status_error($repo, 1)) {
        warn "Hard Eng enforcement check failed: $learning_error\n";
        exit 4;
    }
    print encode_json({ schema_version => 1, rules => $coverage });
    exit 0;
}
if (($ARGV[0] // '') eq 'coverage') {
    require Cwd;
    my $repo = absolute_path(Cwd::getcwd(), $ARGV[1] // '.');
    my ($coverage, $error) = coverage_status($repo);
    if ($error) {
        warn "Hard Eng enforcement coverage failed: $error\n";
        exit 4;
    }
    print encode_json({ schema_version => 1, rules => $coverage });
    exit 0;
}
exit hook_main(@ARGV);
