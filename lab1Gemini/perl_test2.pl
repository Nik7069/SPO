#!/usr/bin/perl
use strict;
use warnings;

my $eps = 0.0001;

print "Введите x: ";
my $x = <STDIN>;
chomp $x;

my $y = $x;          # Начальные установки
my $n = 2;
my $vs = $x;

do {
    $vs = -$vs * $x * $x / (2 * $n - 1) / (2 * $n - 2);  # Формирование слагаемого
    $n = $n + 1;
    $y = $y + $vs;
} until (abs($vs) < $eps);  # Выход из цикла по выполнению условия

print "$x $y $eps\n";