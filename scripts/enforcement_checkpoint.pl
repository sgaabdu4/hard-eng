use strict;
use warnings;

sub learning_status_error_impl {
    my ($repo, $closure) = @_;
    return undef unless -e "$repo/.agents/learning";
    require Cwd;
    my $tool = Cwd::abs_path(__FILE__);
    $tool =~ s{scripts/enforcement_checkpoint\.pl\z}{skills/he-learn/scripts/learning_state.py};
    return 'Hard Eng learning validator is missing'
        unless -f $tool && !-l $tool;
    my @command = ('python3', $tool, 'validate');
    push @command, '--closure' if $closure;
    push @command, '--repo', $repo;
    open my $check, '-|', @command
        or return 'cannot run the Hard Eng learning validator';
    local $/;
    my $output = <$check> // '';
    return undef if close $check;
    return "repository learning state is invalid; run ~/.agents/setup.sh repo-check $repo";
}

sub coverage_status_impl {
    my ($repo) = @_;
    my $data;
    eval { $data = decode_json(slurp("$repo/hard-eng.gates.json")); 1 }
        or return ({}, 'hard-eng.gates.json is invalid');
    my $coverage = ref($data) eq 'HASH' && ref($data->{enforcement}) eq 'HASH'
        ? $data->{enforcement}{coverage} : undef;
    return ({}, 'enforcement coverage must be a nonempty rule object')
        unless ref($coverage) eq 'HASH' && keys %$coverage;
    my %rules;
    for my $name (sort keys %$coverage) {
        my $record = $coverage->{$name};
        return ({}, "invalid enforcement coverage rule: $name")
            unless $name =~ /\A[a-z0-9]+(?:-[a-z0-9]+)*\z/
                && ref($record) eq 'ARRAY' && @$record == 3;
        my ($mode, $owner, $proof) = @$record;
        return ({}, "invalid enforcement boundary for $name")
            unless defined($mode) && !ref($mode) && $mode =~ /\A(?:block|checkpoint check)\z/;
        for my $path ($owner, $proof) {
            return ({}, "missing regular enforcement owner/proof for $name: " . ($path // ''))
                if !defined($path) || ref($path) || $path =~ m{\A/|(?:\A|/)\.\.(?:/|\z)}
                    || !-f "$repo/$path" || -l "$repo/$path";
        }
        $rules{$name} = $mode;
    }
    return (\%rules, undef);
}

sub changed_source_error_impl {
    my ($repo, $active) = @_;
    my ($direct) = direct_route(
        $repo,
        $ENV{HARD_ENG_SESSION_ID} // '',
        $ENV{HARD_ENG_REQUEST_DIGEST} // '',
    ) unless $active;
    if ($active && $active->{state} eq 'green') {
        my $python = trusted_python();
        return 'trusted Python is unavailable for green snapshot validation'
            unless defined $python;
        my $tool = "$repo/skills/he/scripts/plan_state.py";
        return 'green snapshot validator is missing or unsafe'
            unless -f $tool && !-l $tool;
        local %ENV = %ENV;
        $ENV{PATH} = trusted_command_path();
        my @command = (
            $python, $tool, 'assert-green', '--repo', $repo,
            '--plan', $active->{path},
            '--artifact-only',
        );
        open my $assertion, '-|', @command
            or return 'cannot run the green snapshot validator';
        local $/;
        my $output = <$assertion> // '';
        return undef if close $assertion;
        $output =~ s/[\x00-\x1f\x7f]+/ /g;
        $output = substr($output, 0, 500);
        return 'green repository snapshot no longer matches the recorded artifact'
            . ($output ne '' ? ": $output" : '');
    }
    local %ENV = %ENV;
    open my $variables, '-|', 'git', '-C', $repo, 'rev-parse', '--local-env-vars'
        or return 'cannot inspect Git environment for the repository checkpoint';
    my @variables = grep { length } map { chomp; $_ } <$variables>;
    close $variables;
    delete @ENV{@variables};
    open my $status, '-|', 'git', '-C', $repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all'
        or return 'cannot inspect repository changes at the checkpoint';
    local $/;
    my $raw = <$status> // '';
    close $status or return 'cannot inspect repository changes at the checkpoint';
    for my $entry (split /\0/, $raw) {
        next if $entry eq '';
        $entry =~ s/\A..\s//;
        my $target = absolute_path($repo, $entry);
        if ($active && $active->{state} =~ /\A(?:planning|build-ready|green)\z/) {
            return "repository path changed outside lifecycle state: $entry"
                unless lifecycle_target_allowed($repo, $active, $target);
            next;
        }
        next if $active;
        return "repository path changed without a current direct-route receipt: $entry"
            unless $direct && direct_allows_target($repo, $direct, $target);
    }
    return undef;
}

1;
