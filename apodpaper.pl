#!/usr/bin/perl
use strict;
use warnings;

use Win32;
use Win32::API;
use LWP::Simple;
require Carp;

# for both constants see winuser.h

use constant SPI_SETDESKWALLPAPER  => 20;
use constant SPIF_UPDATEANDSENDINI => 3; # SPIF_UPDATEINIFILE || SPIF_SENDWININICHANGE

my $apodbase = 'http://apod.nasa.gov/';
my $dlbase = 'c:/Users/mmeyer/Downloads';
my $dlbasew = 'c:\\Users\\mmeyer\\Downloads\\';

chdir $dlbase or die "Couldnt chdir to $dlbase: $!";

my $content = get($apodbase) or die "Couldn't download image: $!";

Carp::croak 'Content doesn\'t match' unless $content =~ m/<IMG SRC="(.*)"/g;

my $urlend = $1;

Carp::croak 'No url found' unless $urlend =~ m|([^/]+)$|;
my $targ = $1;

my $status = getstore($apodbase . $urlend, $targ);
Carp::croak "Couldn't store image: $status" unless is_success($status);

my $spf = Win32::API->new('user32','SystemParametersInfo', 'IIPI', 'I')
  or Carp::croak "Could not import function.\n";

$spf->Call(SPI_SETDESKWALLPAPER, 0, $dlbasew . $targ, SPIF_UPDATEANDSENDINI)
  or Carp::croak "Could not set wallpaper:\n" . Win32::GetLastError();

exit;
