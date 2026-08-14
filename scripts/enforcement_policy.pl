#!/usr/bin/env perl
use strict;
use warnings;

our %SOURCE = map { $_ => 1 } qw(
    .bash .c .cc .cjs .cpp .cs .css .dart .go .h .hpp .java .js .jsx .kt .kts
    .m .mjs .mm .php .py .rb .rs .scala .scss .sh .svelte .swift .ts .tsx .vue .zsh
);

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
    open my $handle, '<', $path or die "$path: $!";
    local $/;
    return <$handle>;
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
    return (0, undef) unless -f $path;
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
    my @autonomous = qw(
        additive-live-data-or-schema build-and-verify commit-push-pr-merge-ci
        named-deployment parallel-subagents planning-and-engineering-decisions
    );
    my $allowed_ok = ref($authorization->{allowed}) eq 'ARRAY'
        && (($authorization->{mode} // '') eq 'autonomous'
            ? join("\0", @{$authorization->{allowed}}) eq join("\0", @autonomous)
            : join("\0", @{$authorization->{allowed}}) eq 'approved-build'
                || join("\0", @{$authorization->{allowed}}) eq "approved-build\0parallel-subagents");
    return 'authorization receipt does not match the approved Feature Brief'
        unless ref($authorization) eq 'HASH'
            && ($authorization->{schema_version} // 0) == 1
            && ($authorization->{plan_id} // '') eq $plan_id
            && ($authorization->{fingerprint} // '') eq $fingerprint
            && ($authorization->{mode} // '') =~ /\A(?:standard|autonomous)\z/
            && ($authorization->{approval_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
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

sub write_decision {
    my ($repo, $targets, $deletes, $session_id) = @_;
    my $status = inspect_repo($repo);
    return undef unless $status->{configured};
    return "Hard Eng blocked this write: $status->{error}. Run ./setup.sh check." if $status->{error};
    return 'Hard Eng blocked this write because the adapter did not provide a target path. Run ./setup.sh check.'
        unless @$targets;
    my $active = @{$status->{active}} ? $status->{active}[0] : undef;
    my ($direct, $direct_error);
    ($direct, $direct_error) = direct_route($repo, $session_id) unless $active;
    for my $target (@$targets) {
        next unless $target eq $repo || index($target, "$repo/") == 0;
        my $relative = substr($target, length($repo) + 1);
        my $new_plan = $relative =~ m{\Afeatures/[^/]+/PLAN\.md\z} && !-e $target;
        if (!$active && !$new_plan) {
            return "Hard Eng blocked this direct write: $direct_error. Start the direct route for this task."
                unless $direct;
            return "Hard Eng blocked this direct write outside its intended paths: $relative."
                unless direct_allows_target($repo, $direct, $target);
        }
        if ($active && $target eq $active->{path} && $deletes->{$target}) {
            return "Hard Eng blocked deleting or renaming active $active->{path}.";
        }
        if ($active && $target =~ /\.md\z/i && index($target, $active->{path} =~ s{/PLAN\.md\z}{}r . '/') == 0 && $target ne $active->{path}) {
            return "Hard Eng blocked an extra Markdown file in the active feature: $target.";
        }
        if ($active && $active->{state} ne 'building') {
            my ($suffix) = $target =~ /(\.[^.\/]+)\z/;
            return "Hard Eng blocked this product write while the Feature Brief is $active->{state}. Move it to building first."
                if $suffix && $SOURCE{lc $suffix};
        }
    }
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

my $PROTECTED_HELPER = __FILE__ =~ s{[^/]+\z}{enforcement_protected.pl}r;
$PROTECTED_HELPER = "./$PROTECTED_HELPER" unless $PROTECTED_HELPER =~ m{\A(?:/|\./|\.\./)};

sub load_protected_helper { require $PROTECTED_HELPER; }
sub protected_approval { load_protected_helper(); return protected_approval_impl(@_); }
sub guard_shell { load_protected_helper(); return guard_shell_impl(@_); }
sub external_protected_kind { load_protected_helper(); return external_protected_kind_impl(@_); }
sub external_mutating { load_protected_helper(); return external_mutating_impl(@_); }
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
    my ($repo, $session_id) = @_;
    my ($receipt) = direct_route($repo, $session_id);
    return 0 unless $receipt && ref($receipt->{allowed}) eq 'ARRAY';
    return scalar grep { defined($_) && !ref($_) && $_ eq 'parallel-subagents' }
        @{$receipt->{allowed}};
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
        my $raw_name = lc($item->{name} // $item->{toolName} // $payload->{tool_name} // $payload->{toolName} // '');
        my $name = $raw_name;
        $name =~ s/^.*(?:__|\.)//;
        if ($name =~ /\A(?:agent|task|spawn_agent|create_agent)\z/) {
            my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
            my $repo = repo_root($cwd);
            next unless $repo && -f "$repo/hard-eng.gates.json";
            my $status = inspect_repo($repo);
            next unless $status->{configured};
            return deny($runtime, "Hard Eng blocked this subagent: $status->{error}.")
                if $status->{error};
            my $active = @{$status->{active}} ? $status->{active}[0] : undef;
            return deny($runtime, "Hard Eng blocked this subagent because the current prompt did not explicitly authorize parallel agents.")
                unless ($active ? subagent_allowed($active) : direct_subagent_allowed(
                    $repo, $payload->{session_id} // $payload->{sessionId} // ''
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
                next if $kind && protected_approval($repo, $active, $kind, $raw_name, $args);
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
                next if protected_approval($repo, $active, $kind, $raw_name, $args);
                return deny($runtime, protected_reason($kind));
            }
            if ($active && external_mutating($name)) {
                my $mode = authorization_mode($active) // 'standard';
                next if $mode eq 'autonomous' && autonomous_external_allowed($name);
                my $kind = 'external-live-write-or-delivery';
                next if protected_approval($repo, $active, $kind, $raw_name, $args);
                return deny($runtime, 'Hard Eng blocked this live write or delivery action. It needs separate exact approval.');
            }
            if (!$active && external_mutating($name)) {
                my $session_id = $payload->{session_id} // $payload->{sessionId} // '';
                my ($direct) = direct_route($repo, $session_id);
                return deny($runtime, $direct
                    ? 'Hard Eng blocked this live write or delivery action. Start a Feature Loop so its target and approval can be recorded.'
                    : 'Hard Eng blocked this external write because this task has no valid route receipt.');
            }
        }
        next unless $name =~ /\A(?:apply_patch|create|create_file|edit|edit_file|multiedit|notebookedit|str_replace|str_replace_editor|write|write_file)\z/;
        next unless $repo && -f "$repo/hard-eng.gates.json";
        $repo = absolute_path('/', $repo);
        my (@targets, %deletes);
        for my $key (qw(file_path filePath path file notebook_path notebookPath)) {
            push @targets, absolute_path($cwd, $args->{$key}) if defined $args->{$key} && !ref($args->{$key});
        }
        for my $body (scalar_strings($args)) {
            next unless defined $body;
            while ($body =~ /^\*\*\* (Add|Update|Delete) File: (.+)$/mg) {
                my $target = absolute_path($cwd, $2);
                push @targets, $target;
                $deletes{$target} = 1 if $1 eq 'Delete';
            }
        }
        @targets = () if $malformed;
        my %seen;
        @targets = grep { !$seen{$_}++ } @targets;
        my $session_id = $payload->{session_id} // $payload->{sessionId} // '';
        my $reason = write_decision($repo, \@targets, \%deletes, $session_id);
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
