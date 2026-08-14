use strict;
use warnings;

our %SOURCE;

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
    return undef if $active && $active->{state} !~ /\A(?:planning|build-ready)\z/;
    my ($direct) = direct_route($repo, undef) unless $active;
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
        $entry =~ s/\A..\s//;
        my ($suffix) = $entry =~ /(\.[^.\/]+)\z/;
        next unless $suffix && $SOURCE{lc $suffix};
        return "product source changed while the Feature Brief is $active->{state}: $entry"
            if $active;
        my $target = absolute_path($repo, $entry);
        return "product source changed without a current direct-route receipt: $entry"
            unless $direct && direct_allows_target($repo, $direct, $target);
    }
    return undef;
}

1;
