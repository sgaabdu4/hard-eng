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

sub direct_route_impl {
    my ($repo, $session_id, $request_digest) = @_;
    return (undef, 'missing direct-route identity')
        unless defined($session_id) && $session_id ne ''
            && defined($request_digest) && $request_digest ne '';
    my ($opened, $output) = direct_owner_impl(
        $repo, 'check-direct', '--repo', $repo,
        '--session-id', $session_id,
        '--request-digest', $request_digest,
    );
    return (undef, 'direct-route receipt does not match this task')
        unless $opened;
    my $receipt;
    eval { $receipt = decode_json($output); 1 }
        or return (undef, 'direct-route validator returned invalid data');
    return (undef, 'direct-route validator returned invalid data')
        unless ref($receipt) eq 'HASH';
    return ($receipt, undef);
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

1;
