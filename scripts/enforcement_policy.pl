#!/usr/bin/env perl
use strict;
use warnings;

my %COVERAGE = (
    'active-plan-delete-or-rename' => 'block',
    'gui-and-unsupported-writers' => 'unsupported',
    'invalid-active-plan' => 'block',
    'malformed-known-write' => 'block',
    'planning-product-write' => 'block',
    'required-enforcement-wiring' => 'block',
    'route-choice' => 'guidance',
    'unknown-or-delayed-writer' => 'checkpoint check',
    'unsafe-git-discard' => 'block',
    'user-intent-provenance' => 'guidance',
);
my %SOURCE = map { $_ => 1 } qw(
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
        }
        my @extra = markdown_files("$features/$folder", $plan);
        return ([], "active feature has extra Markdown file: " . normalise($extra[0])) if @extra;
        push @active, { path => normalise($plan), state => $state };
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

sub write_decision {
    my ($repo, $targets, $deletes) = @_;
    my $status = inspect_repo($repo);
    return undef unless $status->{configured};
    return "Hard Eng blocked this write: $status->{error}. Run ./setup.sh check." if $status->{error};
    return 'Hard Eng blocked this write because the adapter did not provide a target path. Run ./setup.sh check.'
        unless @$targets;
    my $active = @{$status->{active}} ? $status->{active}[0] : undef;
    for my $target (@$targets) {
        next unless $target eq $repo || index($target, "$repo/") == 0;
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

sub guard_shell {
    my ($command, $repo) = @_;
    if ($command =~ /(?:^|[;&|]\s*|\bsudo\s+|\benv\s+)rg\s+(-[A-Za-z]*r[A-Za-z]+)/) {
        return "Blocked $1: ripgrep uses -r for --replace, not recursion. Use rg -n; rg recurses by default.";
    }
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?=[^;&|]*(?:--worktree|-[A-Za-z]*W))/
        || $command =~ /\bgit(?:\s+-C\s+\S+)?\s+restore\b(?![^;&|]*--staged(?:\s|$))(?![^;&|]*-[A-Za-z]*S)(?![^;&|]*--source\b)/) {
        return "Blocked git restore: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.";
    }
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+clean\b(?![^;&|]*(?:-[^\s]*[nN]|--dry-run))/) {
        return "Blocked git clean: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.";
    }
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+(reset\s+--hard|checkout\s+--|stash\s+(?:drop|clear))\b/) {
        my $action = $1;
        $action =~ s/\s.*//;
        return "Blocked git $action: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.";
    }
    if ($command =~ /\bgit(?:\s+-C\s+\S+)?\s+checkout\s+(?!-b\b|-B\b|--branch\b|--orphan\b|--detach\b)(?:\.\.?\/[^;&|\s]+|[^;&|\s]*\.[A-Za-z0-9_-]+)(?:\s|$)/) {
        return "Blocked git checkout of a file: it can discard uncommitted work. Keep the work or get the user's clear confirmation first.";
    }
    if ($repo && $command =~ /\b(?:rm|unlink|mv|git\s+mv)\b/) {
        my $status = inspect_repo($repo);
        if ($status->{configured} && !$status->{error} && @{$status->{active}}) {
            my $plan = $status->{active}[0]{path};
            my $relative = substr($plan, length($repo) + 1);
            return "Hard Eng blocked deleting or renaming active $plan."
                if $command =~ /(?:^|[\s'\"])(?:\.\/)?\Q$relative\E(?:[\s'\"]|$)/
                    || $command =~ /(?:^|[\s'\"])\Q$plan\E(?:[\s'\"]|$)/;
        }
    }
    return undef;
}

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
    for my $item (@items) {
        next unless ref($item) eq 'HASH';
        my $name = $item->{name} // $item->{toolName} // $payload->{tool_name} // $payload->{toolName} // '';
        $name = lc $name;
        $name =~ s/^.*__//;
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
            my $reason = guard_shell($command, repo_root($cwd));
            return deny($runtime, $reason) if $reason;
            next;
        }
        next unless $name =~ /\A(?:apply_patch|create|create_file|edit|edit_file|multiedit|notebookedit|str_replace|str_replace_editor|write|write_file)\z/;
        my $cwd = $payload->{cwd} // $payload->{workingDirectory} // '.';
        my $repo = repo_root($cwd);
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
        my $reason = write_decision($repo, \@targets, \%deletes);
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
    print encode_json({ schema_version => 1, rules => \%COVERAGE });
    exit 0;
}
if (($ARGV[0] // '') eq 'coverage') {
    print encode_json({ schema_version => 1, rules => \%COVERAGE });
    exit 0;
}
exit hook_main(@ARGV);
