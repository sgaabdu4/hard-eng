use strict;
use warnings;

sub git_private_path_impl {
    my ($repo, $name) = @_;
    my $git = "$repo/.git";
    if (-f $git && !-l $git) {
        my $text;
        eval { $text = slurp($git); 1 } or return undef;
        return undef unless $text =~ /\Agitdir:\s*(.+?)\s*\z/;
        $git = absolute_path($repo, $1);
    }
    return undef unless -d $git && !-l $git;
    return "$git/hard-eng/$name";
}

sub direct_route_impl {
    my ($repo, $session_id) = @_;
    my $path = git_private_path_impl($repo, 'current-direct.json');
    return (undef, 'missing direct-route receipt') unless $path && -f $path && !-l $path;
    my $receipt;
    eval { $receipt = decode_json(slurp($path)); 1 }
        or return (undef, 'invalid direct-route receipt');
    return (undef, 'invalid direct-route receipt') unless ref($receipt) eq 'HASH';
    require POSIX;
    my $today = POSIX::strftime('%Y-%m-%d', localtime);
    my @stops = qw(
        account-or-permission-change data-deletion-or-destructive-schema
        force-or-history-rewrite material-payment-or-spend
        protected-live-write-retry secret-exposure
    );
    my $session_ok = !defined($session_id) || $session_id eq '';
    if (!$session_ok) {
        require Digest::SHA;
        $session_ok = ($receipt->{session_digest} // '') eq
            'sha256:' . Digest::SHA::sha256_hex($session_id);
    }
    my $allowed = ref($receipt->{allowed}) eq 'ARRAY'
        ? join("\0", @{$receipt->{allowed}}) : '';
    my $sources_ok = ref($receipt->{sources}) eq 'ARRAY' && @{$receipt->{sources}}
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$receipt->{sources}});
    my $versions_ok = ref($receipt->{source_versions}) eq 'ARRAY'
        && $sources_ok && @{$receipt->{source_versions}} == @{$receipt->{sources}}
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$receipt->{source_versions}});
    my $verified_ok = ref($receipt->{verified}) eq 'ARRAY' && @{$receipt->{verified}}
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$receipt->{verified}});
    my $unknown_ok = ref($receipt->{unknown}) eq 'ARRAY'
        && !(grep { !defined($_) || ref($_) || $_ eq '' } @{$receipt->{unknown}});
    my $local_versions_ok = ($receipt->{scope} // '') ne 'local';
    if (($receipt->{scope} // '') eq 'local' && $versions_ok) {
        require Digest::SHA;
        $local_versions_ok = 1;
        for my $index (0 .. $#{$receipt->{sources}}) {
            my $source = $receipt->{sources}[$index];
            if ($source =~ m{\A/|(?:\A|/)\.\.(?:/|\z)}) {
                $local_versions_ok = 0; last;
            }
            my $source_path = absolute_path($repo, $source);
            if (index($source_path, "$repo/") != 0 || !-f $source_path || -l $source_path) {
                $local_versions_ok = 0; last;
            }
            open my $source_handle, '<', $source_path or do { $local_versions_ok = 0; last; };
            binmode $source_handle;
            my $digest = Digest::SHA->new(256)->addfile($source_handle)->hexdigest;
            close $source_handle;
            if ($receipt->{source_versions}[$index] ne "sha256:$digest") {
                $local_versions_ok = 0; last;
            }
        }
    }
    my $intended_ok = ref($receipt->{intended_paths}) eq 'ARRAY'
        && @{$receipt->{intended_paths}}
        && !(grep {
            ref($_) ne 'HASH'
                || ($_->{path} // '') eq '' || ref($_->{path})
                || $_->{path} =~ m{\A/|(?:\A|/)\.\.(?:/|\z)}
                || ($_->{scope} // '') !~ /\A(?:file|tree)\z/
        } @{$receipt->{intended_paths}});
    return (undef, 'direct-route receipt does not match this task')
        unless ($receipt->{schema_version} // 0) == 1
            && ($receipt->{route} // '') eq 'direct'
            && ($receipt->{session_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && ($receipt->{request_digest} // '') =~ /\Asha256:[0-9a-f]{64}\z/
            && $session_ok
            && ($receipt->{checked_at} // '') =~ /\A\d{4}-\d{2}-\d{2}\z/
            && ($receipt->{fresh_until} // '') =~ /\A\d{4}-\d{2}-\d{2}\z/
            && $receipt->{checked_at} le $today && $today le $receipt->{fresh_until}
            && ($receipt->{scope} // '') =~ /\A(?:local|external)\z/
            && $sources_ok && $versions_ok && $local_versions_ok && $verified_ok && $unknown_ok
            && (($receipt->{scope} // '') eq 'local'
                || !(grep { $_ !~ m{\Ahttps://} } @{$receipt->{sources}}))
            && ($receipt->{question} // '') ne '' && !ref($receipt->{question})
            && ($receipt->{decision} // '') ne '' && !ref($receipt->{decision})
            && ($receipt->{repository_head} // '') ne '' && !ref($receipt->{repository_head})
            && $intended_ok
            && ($allowed eq 'reversible-local-work'
                || $allowed eq "reversible-local-work\0parallel-subagents")
            && ref($receipt->{stop_before}) eq 'ARRAY'
            && join("\0", @{$receipt->{stop_before}}) eq join("\0", @stops);
    return ($receipt, undef);
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

1;
