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
            next if -f $path && $path =~ m{\A\Q$folder\E/tickets/T-(?:[1-9][0-9]*|int)\.md\z};
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
        data-deletion-or-destructive-schema force-or-history-rewrite
        machine-scope-write secret-exposure
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
    return 1 if $relative =~ m{\Afeatures/\Q$feature\E/tickets/T-(?:[1-9][0-9]*|int)\.md\z};
    return 1 if $relative =~ m{\A\.agents/learning/[a-z0-9]+(?:-[a-z0-9]+)*\.json\z};
    return 0;
}

# A write outside the governed repository changes the machine, not the branch, so
# it survives every revert and leaks into unrelated work. Scratch and agent memory
# are the only destinations that carry no cross-repository effect.
sub machine_scope_allowed {
    my ($target) = @_;
    for my $root ('/tmp', '/private/tmp', '/var/folders', '/private/var/folders') {
        return 1 if index($target, "$root/") == 0;
    }
    my $tmpdir = $ENV{TMPDIR};
    if (defined($tmpdir) && $tmpdir ne '') {
        $tmpdir = normalise($tmpdir);
        return 1 if $tmpdir ne '' && index($target, "/$tmpdir/") == 0;
    }
    return 1 if $target =~ m{\A/[^/]+/[^/]+/\.claude/projects/[^/]+/memory/};
    return 0;
}

sub write_decision {
    my ($repo, $targets, $deletes, $session_id, $request_digest) = @_;
    my $status = inspect_repo($repo);
    return undef unless $status->{configured};
    my $active = !$status->{error} && @{$status->{active}} ? $status->{active}[0] : undef;
    for my $target (@$targets) {
        if ($target ne $repo && index($target, "$repo/") != 0) {
            next if machine_scope_allowed($target);
            return "Hard Eng blocked writing $target because it sits outside this repository and changes the machine for every other repository. Tell the user the exact path and its machine-wide effect, get their plain yes, then record it with execution_evidence.py approve-protected --kind machine-scope-write.";
        }
        my $relative = substr($target, length($repo) + 1);
        return 'Hard Eng blocked this raw write to lifecycle-owned PLAN.md or receipt state. Use the lifecycle command owner.'
            if $relative =~ m{\Afeatures/[a-z0-9]+(?:-[a-z0-9]+)*/(?:PLAN\.md|receipts/[a-z0-9][a-z0-9._-]*\.json|tickets/T-(?:[1-9][0-9]*|int)\.md)\z};
        return "Hard Eng blocked permanently deleting active $active->{path}."
            if $active && $target eq $active->{path} && $deletes->{$target};
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

# Advisory context is Claude-only, once per session per repository; the marker
# is written only when the notice actually prints, so a denied batch keeps it.
sub advise_pending {
    my ($runtime, $payload, $repo) = @_;
    return undef unless ($runtime // '') eq 'claude';
    my $session = $payload->{session_id} // $payload->{sessionId} // '';
    $session = 'no-session' if $session eq '';
    require Digest::SHA;
    my $base = $ENV{TMPDIR};
    $base = '/tmp' unless defined($base) && $base ne '' && -d $base;
    $base =~ s{/+\z}{};
    my $marker = "$base/hard-eng-advise-" . Digest::SHA::sha256_hex("$session\0$repo");
    return undef if -e $marker;
    return { marker => $marker, repo => $repo };
}

sub advise_output {
    my ($advise) = @_;
    require Fcntl;
    if (sysopen my $marker, $advise->{marker}, Fcntl::O_WRONLY() | Fcntl::O_CREAT() | Fcntl::O_EXCL()) {
        close $marker;
    }
    print encode_json({ hookSpecificOutput => {
        hookEventName => 'PreToolUse',
        additionalContext => "This work targets a repository without Hard Eng gate wiring ($advise->{repo}/hard-eng.gates.json is missing), so no gates, receipts, or checkpoints run there. Durable product or feature work routes through the he skill; its feature setup wires the gates via gate-migration. Bounded direct work runs deterministic-checks gate-migration first, then records a direct receipt. This notice appears once per session.",
    } });
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
sub protected_reason { load_protected_helper(); return protected_reason_impl(@_); }

sub scalar_strings {
    my ($value) = @_;
    return ($value) unless ref($value);
    return map { scalar_strings($_) } @$value if ref($value) eq 'ARRAY';
    return map { scalar_strings($_) } values %$value if ref($value) eq 'HASH';
    return ();
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
    my $advise;
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
            $advise ||= advise_pending($runtime, $payload, $repo // absolute_path('/', $cwd))
                if !($repo && -f "$repo/hard-eng.gates.json")
                    && $command =~ /(?:\A|[\s;&|(`])git(?:\s+-C\s+\S+|\s+--?[^\s;&|`]+)*\s+init(?:[\s;&|)]|\z)/;
            next;
        }
        my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
        my $repo = repo_root($cwd);
        if ($raw_name =~ /(?:__|\.)/ && $repo && -f "$repo/hard-eng.gates.json") {
            my $status = inspect_repo($repo);
            my $active = $status->{configured} && !$status->{error} && @{$status->{active}}
                ? $status->{active}[0] : undef;
            if (my $kind = external_protected_kind($raw_name, $name, $args)) {
                next if $active && protected_approval(
                    $repo, $active, $kind, $raw_name, $args,
                    $payload->{session_id} // $payload->{sessionId} // '',
                    $payload->{request_digest} // $payload->{requestDigest} // '',
                );
                return deny($runtime, protected_reason($kind));
            }
            next;
        }
        next unless $name =~ /\A(?:apply_patch|create|create_file|edit|edit_file|multiedit|notebookedit|str_replace|str_replace_editor|write|write_file)\z/;
        if ($repo && !-f "$repo/hard-eng.gates.json") {
            $advise ||= advise_pending($runtime, $payload, $repo);
            next;
        }
        my $governed = defined $repo;
        $repo = absolute_path('/', $repo) if $governed;
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
        @targets = () if $malformed;
        my %seen;
        @targets = grep { !$seen{$_}++ } @targets;
        if ($governed) {
            return deny($runtime, 'Hard Eng blocked this write because its path contains a symlink or invalid component. Active PLAN.md aliases are not writable.')
                if $unsafe_target;
            my $session_id = $payload->{session_id} // $payload->{sessionId} // '';
            my $reason = write_decision(
                $repo, \@targets, \%deletes, $session_id,
                $payload->{request_digest} // $payload->{requestDigest} // '',
            );
            return deny($runtime, $reason) if $reason;
        }
        next if $advise;
        for my $target (@targets) {
            my $target_repo = repo_root($target);
            next unless $target_repo && !-f "$target_repo/hard-eng.gates.json";
            $advise = advise_pending($runtime, $payload, $target_repo);
            last if $advise;
        }
    }
    return advise_output($advise) if $advise;
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
