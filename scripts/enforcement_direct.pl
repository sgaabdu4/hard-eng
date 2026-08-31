use strict;
use warnings;

sub direct_owner_impl {
    my ($repo, @arguments) = @_;
    require Cwd;
    my $helper = Cwd::abs_path(__FILE__) // __FILE__;
    my $owner = $helper =~ s{scripts/enforcement_direct\.pl\z}{skills/he/scripts/execution_evidence.py}r;
    my $bounded = $helper =~ s{scripts/enforcement_direct\.pl\z}{skills/deterministic-checks/scripts/bounded_run.py}r;
    my $python = trusted_python();
    return (0, '') if $owner eq $helper || $bounded eq $helper
        || !defined($python) || !-f $owner || !-f $bounded;
    my @command = (
        $python, $bounded, '--timeout', '15', '--cwd', $repo, '--',
        $python, $owner, @arguments,
    );
    local %ENV = %ENV;
    $ENV{PATH} = trusted_command_path();
    my $null_path = $^O eq 'MSWin32' ? 'NUL' : '/dev/null';
    open my $null, '>', $null_path or return (0, '');
    open my $saved_stderr, '>&', \*STDERR or return (0, '');
    open STDERR, '>&', $null or return (0, '');
    my $output = '';
    my $opened = 0;
    eval {
        open my $reader, '-|', @command or die "cannot start direct-route validator";
        local $/;
        $output = <$reader> // '';
        close $reader;
        $opened = $? == 0;
        1;
    };
    open STDERR, '>&', $saved_stderr or return (0, '');
    close $null;
    return ($opened, $output);
}

sub direct_git_dir_impl {
    my ($repo) = @_;
    my $dotgit = "$repo/.git";
    return undef if -l $dotgit;
    return $dotgit if -d $dotgit;
    return undef unless -f $dotgit;
    my $text;
    eval { $text = slurp($dotgit); 1 } or return undef;
    return undef unless $text =~ /\Agitdir: ([^\r\n]+)\r?\n?\z/;
    my $git_dir = absolute_path($repo, $1);
    return -d $git_dir && !-l $git_dir ? $git_dir : undef;
}

sub direct_common_dir_impl {
    my ($git_dir) = @_;
    my $path = "$git_dir/commondir";
    return $git_dir unless -e $path;
    return undef if -l $path || !-f $path;
    my $text;
    eval { $text = slurp($path); 1 } or return undef;
    return undef unless $text =~ /\A([^\r\n]+)\r?\n?\z/;
    my $common = absolute_path($git_dir, $1);
    return -d $common && !-l $common ? $common : undef;
}

sub direct_receipt_path_impl {
    my ($repo) = @_;
    my $git_dir = direct_git_dir_impl($repo) // return undef;
    return "$git_dir/hard-eng/current-direct.json";
}

sub direct_receipt_present_impl {
    my ($repo) = @_;
    my $path = direct_receipt_path_impl($repo);
    return defined($path) && (-e $path || -l $path) ? 1 : 0;
}

sub direct_canonical_path_impl {
    my ($path) = @_;
    return undef if !defined($path) || ref($path) || $path eq ''
        || $path =~ m{\A/|(?:\A|/)\.\.(?:/|\z)};
    my $canonical = normalise("/$path");
    $canonical =~ s{\A/}{};
    return $canonical eq $path ? $path : undef;
}

sub direct_external_actions_impl {
    my ($receipt) = @_;
    my $actions = exists($receipt->{external_actions}) ? $receipt->{external_actions} : [];
    return undef unless ref($actions) eq 'ARRAY';
    my %seen;
    for my $entry (@$actions) {
        return undef unless ref($entry) eq 'HASH'
            && join("\0", sort keys %$entry) eq join("\0", qw(action_digest effect tool_name))
            && ($entry->{tool_name} // '') ne '' && !ref($entry->{tool_name})
            && $entry->{tool_name} eq lc($entry->{tool_name})
            && ($entry->{action_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && ($entry->{effect} // '') =~ /\A[[:print:]]{1,500}\z/
            && $entry->{effect} eq ($entry->{effect} =~ s/\A\s+|\s+\z//gr);
        my $identity = "$entry->{tool_name}\0$entry->{action_digest}";
        return undef if $seen{$identity}++;
    }
    return $actions;
}

sub direct_route_impl {
    my ($repo, $session_id, $request_digest) = @_;
    my $present = direct_receipt_present_impl($repo);
    return (undef, 'missing direct-route receipt', 0) unless $present;
    my $path = direct_receipt_path_impl($repo);
    my $receipt;
    eval { $receipt = decode_json(slurp($path)); 1 }
        or return (undef, 'direct-route receipt is invalid', 1);
    return (undef, 'direct-route receipt is invalid', 1) unless ref($receipt) eq 'HASH';
    require Cwd;
    require Digest::SHA;
    my $repo_real = Cwd::abs_path($repo);
    my $git_dir = direct_git_dir_impl($repo);
    my $git_real = defined($git_dir) ? Cwd::abs_path($git_dir) : undef;
    my $common = defined($git_dir) ? direct_common_dir_impl($git_dir) : undef;
    my $common_real = defined($common) ? Cwd::abs_path($common) : undef;
    my $context = $receipt->{repository_context};
    my $intended = $receipt->{intended_paths};
    my $sources = $receipt->{sources};
    my $versions = $receipt->{source_versions};
    my $external = direct_external_actions_impl($receipt);
    my $valid = defined($repo_real) && defined($git_real) && defined($common_real)
        && ($receipt->{schema_version} // 0) == 2
        && ($receipt->{route} // '') eq 'direct'
        && ((!defined($session_id) || $session_id eq '')
            || ($receipt->{session_digest} // '') eq 'sha256:' . Digest::SHA::sha256_hex($session_id))
        && ((!defined($request_digest) || $request_digest eq '')
            || (($receipt->{request_digest} // '') eq $request_digest
                && $request_digest =~ /\Asha256:[0-9a-f]{64}\z/))
        && ref($context) eq 'HASH'
        && ($context->{checkout_digest} // '') eq 'sha256:' . Digest::SHA::sha256_hex("$repo_real\0$git_real")
        && ($context->{repository_digest} // '') eq 'sha256:' . Digest::SHA::sha256_hex($common_real)
        && ($receipt->{expires_at_epoch} // 0) >= time
        && ref($sources) eq 'ARRAY' && @$sources
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @$sources)
        && ref($versions) eq 'ARRAY' && @$versions == @$sources
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @$versions)
        && ref($intended) eq 'ARRAY' && @$intended
        && defined($external)
        && ref($receipt->{allowed}) eq 'ARRAY'
        && (join("\0", @{$receipt->{allowed}}) eq 'reversible-local-work'
            || join("\0", @{$receipt->{allowed}}) eq "reversible-local-work\0parallel-subagents")
        && ref($receipt->{stop_before}) eq 'ARRAY'
        && join("\0", @{$receipt->{stop_before}}) eq join("\0", qw(
            data-deletion-or-destructive-schema force-or-history-rewrite machine-scope-write secret-exposure
        ))
        && ($receipt->{write_nonce} // '') =~ /\Asha256:[0-9a-f]{64}\z/
        && ($receipt->{question} // '') ne '' && !ref($receipt->{question})
        && ($receipt->{decision} // '') ne '' && !ref($receipt->{decision})
        && ($receipt->{repository_head} // '') ne '' && !ref($receipt->{repository_head});
    if ($valid) {
        for my $entry (@$intended) {
            $valid = 0, last unless ref($entry) eq 'HASH'
                && defined(direct_canonical_path_impl($entry->{path}))
                && ($entry->{scope} // '') =~ /\A(?:file|tree)\z/;
        }
    }
    return (undef, 'direct-route receipt does not match this task', 1) unless $valid;
    return ($receipt, undef, 1);
}

sub direct_checkpoint_route_impl {
    my ($repo, $session_id, $request_digest) = @_;
    my ($receipt, $error, $present) = direct_route_impl($repo, $session_id, $request_digest);
    return ($receipt, $error, $present) unless $receipt;
    my $scope = $receipt->{scope} // '';
    if ($scope eq 'external') {
        return (undef, 'direct-route receipt has invalid external research sources', 1)
            if grep { $_ !~ m{\Ahttps://} } @{$receipt->{sources}};
    } elsif ($scope eq 'local') {
        require Digest::SHA;
        for my $index (0 .. $#{$receipt->{sources}}) {
            my $source = direct_canonical_path_impl($receipt->{sources}[$index]);
            return (undef, 'direct-route receipt has invalid local research sources', 1)
                unless defined $source;
            my $path = "$repo/$source";
            return (undef, "direct local research source changed: $source", 1)
                unless -f $path && !-l $path;
            my $content;
            eval { $content = slurp($path); 1 }
                or return (undef, "direct local research source changed: $source", 1);
            return (undef, "direct local research source changed: $source", 1)
                unless $receipt->{source_versions}[$index]
                    eq 'sha256:' . Digest::SHA::sha256_hex($content);
        }
    } else {
        return (undef, 'direct-route receipt has an invalid research scope', 1);
    }
    local %ENV = %ENV;
    open my $variables, '-|', 'git', '-C', $repo, 'rev-parse', '--local-env-vars'
        or return (undef, 'cannot inspect Git environment for the direct checkpoint', 1);
    my @variables = grep { length } map { chomp; $_ } <$variables>;
    close $variables;
    delete @ENV{@variables};
    $ENV{PATH} = trusted_command_path();
    open my $head_reader, '-|', 'git', '-C', $repo, 'rev-parse', '--verify', 'HEAD'
        or return (undef, 'cannot inspect the repository revision for the direct checkpoint', 1);
    my $head = <$head_reader> // '';
    chomp $head;
    $head = 'unborn' unless close $head_reader;
    return (undef, 'direct-route receipt no longer matches the repository revision', 1)
        unless $head ne '' && $head eq ($receipt->{repository_head} // '');
    return ($receipt, undef, 1);
}

sub consume_direct_route_impl {
    my ($repo, $receipt, $session_id, $request_digest) = @_;
    return 0 unless ref($receipt) eq 'HASH'
        && ($receipt->{write_nonce} // '') =~ /\Asha256:[0-9a-f]{64}\z/;
    my ($opened) = direct_owner_impl(
        $repo, 'consume-direct', '--repo', $repo,
        '--session-id', $session_id,
        '--request-digest', $request_digest,
        '--write-nonce', $receipt->{write_nonce},
    );
    return $opened ? 1 : 0;
}

sub direct_allows_target_impl {
    my ($repo, $receipt, $target) = @_;
    return 1 unless $target eq $repo || index($target, "$repo/") == 0;
    my $relative = substr($target, length($repo) + 1);
    for my $entry (@{$receipt->{intended_paths}}) {
        next unless ref($entry) eq 'HASH';
        my $path = $entry->{path} // '';
        next if ref($path) || $path eq '' || $path =~ m{\A/|(?:\A|/)\.\.(?:/|\z)};
        return 1 if ($entry->{scope} // '') eq 'file' && $relative eq $path;
        return 1 if ($entry->{scope} // '') eq 'tree'
            && ($relative eq $path || index($relative, "$path/") == 0);
    }
    return 0;
}

sub external_state_change_impl {
    my ($raw_name, $name) = @_;
    return 0 unless ($raw_name // '') =~ /\Amcp(?:__|\.)/;
    my @parts = split /_+/, ($name // '');
    my %verbs = map { $_ => 1 } qw(
        add approve archive cancel charge close comment connect consume create deploy disable disconnect
        edit enable fork generate grant handoff import install invite merge move patch pause pay publish purchase
        reject release remove rename reorder reply resolve restore resume revoke save send set share submit
        trigger unarchive uninstall update upload write
    );
    my %reads = map { $_ => 1 } qw(check fetch find get inspect list lookup preview query read search status view);
    return 0 if @parts && $reads{$parts[0]} && !$verbs{$parts[-1]};
    return scalar grep { $verbs{$_} } @parts;
}

sub direct_allows_external_action_impl {
    my ($receipt, $tool_name, $digest) = @_;
    my $actions = direct_external_actions_impl($receipt) // return 0;
    my $canonical_tool = lc($tool_name // '');
    for my $entry (@$actions) {
        return 1 if $entry->{tool_name} eq $canonical_tool && $entry->{action_digest} eq $digest;
    }
    return 0;
}

1;
