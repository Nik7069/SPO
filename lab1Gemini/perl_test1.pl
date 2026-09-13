#!/usr/bin/perl
use strict;
use warnings;

sub tokenize {
    my ($expr) = @_;
    my @tokens;
    while ($expr =~ /\S/g) {
        if ($expr =~ /\G(\d+(?:\.\d+)?)/gc) {
            push @tokens, $1;
        } elsif ($expr =~ /\G([\+\-\*\/\(\)])/gc) {
            push @tokens, $1;
        } else {
            my $pos = pos($expr) || 0;
            die "Ошибка: неверный символ '" . substr($expr, $pos, 1) . "' на позиции $pos\n";
        }
    }
    return \@tokens;
}

sub parse_expr {
    my ($tokens) = @_;
    my $val = parse_term($tokens);
    while (@$tokens && ($tokens->[0] eq '+' || $tokens->[0] eq '-')) {
        my $op = shift @$tokens;
        my $rhs = parse_term($tokens);
        $val = ($op eq '+') ? $val + $rhs : $val - $rhs;
    }
    return $val;
}

sub parse_term {
    my ($tokens) = @_;
    my $val = parse_factor($tokens);
    while (@$tokens && ($tokens->[0] eq '*' || $tokens->[0] eq '/')) {
        my $op = shift @$tokens;
        my $rhs = parse_factor($tokens);
        die "Ошибка: деление на ноль\n" if $op eq '/' && $rhs == 0;
        $val = ($op eq '*') ? $val * $rhs : $val / $rhs;
    }
    return $val;
}

sub parse_factor {
    my ($tokens) = @_;
    die "Ошибка: незавершённое выражение\n" unless @$tokens;
    my $token = shift @$tokens;

    if ($token eq '-') {
        return -parse_factor($tokens);
    } elsif ($token eq '+') {
        return parse_factor($tokens);
    } elsif ($token eq '(') {
        my $val = parse_expr($tokens);
        die "Ошибка: нет закрывающей скобки\n"
            unless @$tokens && shift(@$tokens) eq ')';
        return $val;
    } elsif ($token =~ /^\d+(?:\.\d+)?$/) {
        return $token + 0;
    } else {
        die "Ошибка: неверный токен '$token'\n";
    }
}

sub evaluate {
    my ($line) = @_;
    my $tokens = tokenize($line);
    die "Ошибка: пустое выражение\n" unless @$tokens;
    my $result = parse_expr($tokens);
    die "Ошибка: синтаксический мусор в конце\n" if @$tokens;
    return $result;
}

print "Console Calculator (Perl)\n";
print "Enter expression or 'exit' to quit.\n\n";

while (1) {
    print "calc> ";
    my $line = <STDIN>;
    last unless defined $line;
    $line =~ s/^\s+|\s+$//g;
    next if $line eq '';
    last if $line =~ /^(?:exit|quit)$/i;

    eval {
        my $res = evaluate($line);
        print "Result: $res\n";
    };
    if ($@) {
        my $err = $@;
        $err =~ s/ at .* line \d+\.\n$//;
        print "$err";
    }
}
