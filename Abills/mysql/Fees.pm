package Fees;
# Finance module
# Fees 

use strict;
use vars qw(@ISA @EXPORT @EXPORT_OK %EXPORT_TAGS $VERSION
);

use Exporter;
$VERSION = 2.00;
@ISA = ('Exporter');

@EXPORT = qw(
);

@EXPORT_OK = ();
%EXPORT_TAGS = ();

use main;
use Bills;
@ISA  = ("main");
use Finance;
@ISA  = ("Finance");


my $Bill;
my $admin;
my $CONF;

#**********************************************************
# Init 
#**********************************************************
sub new {
  my $class = shift;
  ($db, $admin, $CONF) = @_;
  my $self = { };
  bless($self, $class);
  
  $Bill=Bills->new($db, $admin, $CONF); 

  return $self;
}


#**********************************************************
#
#**********************************************************
sub defaults {
  my $self = shift;

  my %DATA = (
   UID             => 0, 
   BILL_ID         => 0,
   SUM             => 0.00,
   DESCRIBE        => '',
   SESSION_IP      => 0.0.0.0,
   DEPOSIT         => 0.00,
   AID             => 0,
   COMPANY_VAT     => 0,
   INNER_DESCRIBE  => '',
   METHOD          => 0
  );

 
  $self = \%DATA;
  return $self;
}

#**********************************************************
# Take sum from bill account
# take()
#**********************************************************
sub take {
  my $self = shift;
  my ($user, $sum, $attr) = @_;
  
  %DATA = $self->get_data($attr, { default => defaults() });
  my $DATE              =  ($attr->{DATE}) ? "'$attr->{DATE}'" : 'now()';
  my $DESCRIBE          = ($DATA{DESCRIBE}) ? $DATA{DESCRIBE} : '';
  $DATA{INNER_DESCRIBE} = '' if (! $DATA{INNER_DESCRIBE});
  
  if ($sum <= 0) {
     $self->{errno} = 12;
     $self->{errstr} = 'ERROR_ENTER_SUM';
     return $self;
   }
  elsif ($user->{UID} <= 0) {
     $self->{errno}  = 18;
     $self->{errstr} = 'ERROR_ENTER_UID';
     return $self;
   }

 
  $sum = sprintf("%.6f", $sum);
  $db->{AutoCommit}=0;
  if ($attr->{BILL_ID}) {
    $user->{BILL_ID} = $attr->{BILL_ID}
   }
  elsif ($CONF->{FEES_PRIORITY}) {
    if ($CONF->{FEES_PRIORITY}=~/^bonus/ && $user->{EXT_BILL_ID}) {
    	if ( $user->{EXT_BILL_ID} && ! defined( $self->{EXT_BILL_DEPOSIT} )  ) {
    		$user->info($user->{UID});
    	 }

      if ($CONF->{FEES_PRIORITY}=~/main/ && $user->{EXT_BILL_DEPOSIT} < $sum) {
      	if( $user->{EXT_BILL_DEPOSIT} > 0) {
      	  $Bill->action('take', $user->{EXT_BILL_ID}, $user->{EXT_BILL_DEPOSIT});
          if($Bill->{errno}) {
            $self->{errno}  = $Bill->{errno};
            $self->{errstr} = $Bill->{errstr};
            return $self;
           }

          $self->{SUM}=$self->{EXT_BILL_DEPOSIT};
          $self->query($db, "INSERT INTO fees (uid, bill_id, date, sum, dsc, ip, last_deposit, aid, vat, inner_describe, method) 
             values ('$user->{UID}', '$user->{EXT_BILL_ID}', $DATE, '$self->{SUM}', '$DESCRIBE', 
              INET_ATON('$admin->{SESSION_IP}'), '$Bill->{DEPOSIT}', '$admin->{AID}',
              '$user->{COMPANY_VAT}', '$DATA{INNER_DESCRIBE}', '$DATA{METHOD}')", 'do');
          $sum = $sum - $user->{EXT_BILL_DEPOSIT};
        }
       }
      else {
        $user->{BILL_ID} = $user->{EXT_BILL_ID};	
       }
     }
    elsif ($CONF->{FEES_PRIORITY}=~/^main,bonus/) {
    	if ( $user->{EXT_BILL_ID} && ! defined( $self->{EXT_BILL_DEPOSIT} )  ) {
    		$user->info($user->{UID});
    	 }

      if ($user->{DEPOSIT} < $sum) {
      	$Bill->action('take', $user->{BILL_ID}, $user->{EXT_BILL_DEPOSIT});
        if($Bill->{errno}) {
          $self->{errno}  = $Bill->{errno};
          $self->{errstr} =  $Bill->{errstr};
          return $self;
         }

        $self->{SUM}=$self->{EXT_BILL_DEPOSIT};
        $self->query($db, "INSERT INTO fees (uid, bill_id, date, sum, dsc, ip, last_deposit, aid, vat, inner_describe, method) 
           values ('$user->{UID}', '$user->{EXT_BILL_ID}', $DATE, '$self->{SUM}', '$DESCRIBE', 
            INET_ATON('$admin->{SESSION_IP}'), '$Bill->{DEPOSIT}', '$admin->{AID}',
            '$user->{COMPANY_VAT}', '$DATA{INNER_DESCRIBE}', '$DATA{METHOD}')", 'do');
        $sum = $sum - $user->{EXT_BILL_DEPOSIT};
        $user->{BILL_ID} = $user->{EXT_BILL_ID};	
       }
     }
   }

 

  if ($user->{BILL_ID} && $user->{BILL_ID} > 0) {
    $Bill->info( { BILL_ID => $user->{BILL_ID} } );
    
    if ($user->{COMPANY_VAT}) {
      $sum = $sum * ((100 + $user->{COMPANY_VAT}) / 100);
     }
    else {
    	$user->{COMPANY_VAT}=0;
     }

    $Bill->action('take', $user->{BILL_ID}, $sum);
    if($Bill->{errno}) {
       $self->{errno}  = $Bill->{errno};
       $self->{errstr} =  $Bill->{errstr};
       return $self;
      }

    $self->{SUM}=$sum;
    $self->query($db, "INSERT INTO fees (uid, bill_id, date, sum, dsc, ip, last_deposit, aid, vat, inner_describe, method) 
           values ('$user->{UID}', '$user->{BILL_ID}', $DATE, '$self->{SUM}', '$DESCRIBE', 
            INET_ATON('$admin->{SESSION_IP}'), '$Bill->{DEPOSIT}', '$admin->{AID}',
            '$user->{COMPANY_VAT}', '$DATA{INNER_DESCRIBE}', '$DATA{METHOD}')", 'do');

    if($self->{errno}) {
      $db->rollback();
      return $self;
     }
    else {
    	$db->commit(); 
     }
   }
  else {
    $self->{errno}=14;
    $self->{errstr}='No Bill';
   }

  $db->{AutoCommit}=1  if (! $attr->{NO_AUTOCOMMIT});

  return $self;
}

#**********************************************************
# del $user, $id
#**********************************************************
sub del {
  my $self = shift;
  my ($user, $id) = @_;

  $self->query($db, "SELECT sum, bill_id from fees WHERE id='$id';");

  if ($self->{TOTAL} < 1) {
     $self->{errno} = 2;
     $self->{errstr} = 'ERROR_NOT_EXIST';
     return $self;
   }
  elsif($self->{errno}) {
     return $self;
   }

  my($sum, $bill_id) = @{ $self->{list}->[0] };
  

  $Bill->action('add', $bill_id, $sum); 

  $self->query($db, "DELETE FROM fees WHERE id='$id';", 'do');
  $admin->action_add($user->{UID}, "FEES:$id SUM:$sum", { TYPE => 10 });

  return $self->{result};
}



#**********************************************************
# list()
#**********************************************************
sub list {
 my $self = shift;
 my ($attr) = @_;

 $SORT = ($attr->{SORT}) ? $attr->{SORT} : 1;
 $DESC = ($attr->{DESC}) ? $attr->{DESC} : '';
 $PG = ($attr->{PG}) ? $attr->{PG} : 0;
 $PAGE_ROWS = ($attr->{PAGE_ROWS}) ? $attr->{PAGE_ROWS} : 25;


 my @list = (); 
 undef @WHERE_RULES;

 if ($attr->{UID}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{UID}, 'INT', 'f.uid') };
  }
 if ($attr->{LOGIN}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{LOGIN}, 'STR', 'u.id') };
  }

 if ($attr->{BILL_ID}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{BILL_ID}, 'INT', 'f.bill_id') };
  }
 elsif ($attr->{COMPANY_ID}) {
 	 push @WHERE_RULES, @{ $self->search_expr($attr->{COMPANY_ID}, 'INT', 'u.company_id') };
  }
 
 if ($attr->{AID}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{AID}, 'INT', 'f.aid') };
  }

 if ($attr->{ID}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{ID}, 'INT', 'f.id') };
  }

 if ($attr->{A_LOGIN}) {
 	 push @WHERE_RULES, @{ $self->search_expr($attr->{A_LOGIN}, 'STR', 'a.id') };
 }

 if ($attr->{DOMAIN_ID}) {
   push @WHERE_RULES, "u.domain_id='$attr->{DOMAIN_ID}' ";
  }

 # Show debeters
 if ($attr->{DESCRIBE}) {
    push @WHERE_RULES, @{ $self->search_expr($attr->{DESCRIBE}, 'STR', 'f.dsc') };
  }

 if ($attr->{INNER_DESCRIBE}) {
    push @WHERE_RULES, @{ $self->search_expr($attr->{INNER_DESCRIBE}, 'STR', 'f.inner_describe') };
  }

 if (defined($attr->{METHOD}) && $attr->{METHOD} >=0) {
    push @WHERE_RULES, "f.method IN ($attr->{METHOD}) ";
  }

 if ($attr->{SUM}) {
    push @WHERE_RULES, @{ $self->search_expr($attr->{SUM}, 'INT', 'f.sum') };
  }

 # Show groups
 if ($attr->{GIDS}) {
   push @WHERE_RULES, "u.gid IN ($attr->{GIDS})";
  }
 elsif ($attr->{GID}) {
   push @WHERE_RULES, "u.gid='$attr->{GID}'";
  }

 # Date
 if ($attr->{FROM_DATE}) {
 	    push @WHERE_RULES, @{ $self->search_expr(">=$attr->{FROM_DATE}", 'DATE', 'date_format(f.date, \'%Y-%m-%d\')') },
   @{ $self->search_expr("<=$attr->{TO_DATE}", 'DATE', 'date_format(f.date, \'%Y-%m-%d\')') };
  }
 elsif ($attr->{DATE}) {
   push @WHERE_RULES, @{ $self->search_expr($attr->{DATE}, 'DATE', 'date_format(f.date, \'%Y-%m-%d\')') };
  }
 # Month
 elsif ($attr->{MONTH}) {
   push @WHERE_RULES, "date_format(f.date, '%Y-%m')='$attr->{MONTH}'";
  }
 
 my $ext_tables  = '';
 my $login_field = '';
 if($attr->{FIO}) {
   $ext_tables = 'LEFT JOIN users_pi pi ON (u.uid=pi.uid)';
   $login_field  = "pi.fio,";  
  }

 $WHERE = ($#WHERE_RULES > -1) ? "WHERE " . join(' and ', @WHERE_RULES)  : '';
 
 $self->query($db, "SELECT f.id, u.id, $login_field f.date, f.dsc, f.sum, f.last_deposit, f.method,
    f.bill_id, 
   if(a.name is NULL, 'Unknown', a.name), 
   INET_NTOA(f.ip),
   f.uid, f.inner_describe
    FROM fees f
    LEFT JOIN users u ON (u.uid=f.uid)
    LEFT JOIN admins a ON (a.aid=f.aid)
    $ext_tables
    $WHERE 
    GROUP BY f.id
    ORDER BY $SORT $DESC LIMIT $PG, $PAGE_ROWS;");

 $self->{SUM}        = '0.00';
 $self->{TOTAL_USERS}= 0;

 return $self->{list}  if ($self->{TOTAL} < 1);
 my $list = $self->{list};

if ($self->{TOTAL} > 0 || $PG > 0 ) {
 $self->query($db, "SELECT count(*), sum(f.sum), count(DISTINCT f.uid) FROM fees f 
  LEFT JOIN users u ON (u.uid=f.uid) 
  LEFT JOIN admins a ON (a.aid=f.aid)
 $WHERE");

 ($self->{TOTAL}, 
  $self->{SUM},
  $self->{TOTAL_USERS}) = @{ $self->{list}->[0] };
}

  return $list;
}

#**********************************************************
# report
#**********************************************************
sub reports {
  my $self = shift;
  my ($attr) = @_;

 $SORT = ($attr->{SORT}) ? $attr->{SORT} : 1;
 $DESC = ($attr->{DESC}) ? $attr->{DESC} : '';
 my $date = '';
 undef @WHERE_RULES;
 
 if ($attr->{GIDS}) {
   push @WHERE_RULES, "u.gid IN ( $attr->{GIDS} )";
  }
 elsif ($attr->{GID}) {
   push @WHERE_RULES, "u.gid='$attr->{GID}'";
  }
 
 if ($attr->{BILL_ID}) {
   push @WHERE_RULES, "f.BILL_ID IN ( $attr->{BILL_ID} )";
  }
 
 if($attr->{DATE}) {
   push @WHERE_RULES, "date_format(f.date, '%Y-%m-%d')='$attr->{DATE}'";
  }
 elsif ($attr->{INTERVAL}) {
 	 my ($from, $to)=split(/\//, $attr->{INTERVAL}, 2);
   push @WHERE_RULES, @{ $self->search_expr(">=$from", 'DATE', 'date_format(f.date, \'%Y-%m-%d\')') },
   @{ $self->search_expr("<=$to", 'DATE', 'date_format(f.date, \'%Y-%m-%d\')') };
  }
 elsif (defined($attr->{MONTH})) {
 	 push @WHERE_RULES, "date_format(f.date, '%Y-%m')='$attr->{MONTH}'";
   $date = "date_format(f.date, '%Y-%m-%d')";
  } 
 else {
 	 $date = "date_format(f.date, '%Y-%m')";
  }

   my $GROUP = 1;
   $attr->{TYPE}='' if (! $attr->{TYPE});
   my $ext_tables = '';

   if ($attr->{TYPE} eq 'HOURS') {
     $date = "date_format(f.date, '%H')";
    }
   elsif ($attr->{TYPE} eq 'DAYS') {
     $date = "date_format(f.date, '%Y-%m-%d')";
    }
   elsif($attr->{TYPE} eq 'METHOD') {
   	 $date = "f.method";   	
    }
   elsif($attr->{TYPE} eq 'ADMINS') {
   	 $date = "a.id";   	
    }
   elsif($attr->{TYPE} eq 'FIO') {
   	 $ext_tables = 'LEFT JOIN users_pi pi ON (u.uid=pi.uid)';
   	 $date  = "pi.fio";  
   	 $GROUP = 5; 	
    }
   elsif($attr->{TYPE} eq 'COMPANIES') {
   	 $ext_tables = 'LEFT JOIN companies c ON (u.company_id=c.id)';
   	 $date  = "c.name";  
    }
   elsif($date eq '') {
     $date = "u.id";   	
    }  
 

  if (defined($attr->{METHODS}) and $attr->{METHODS} ne '') {
    push @WHERE_RULES, "f.method IN ($attr->{METHODS}) ";
   }

  my $WHERE = ($#WHERE_RULES > -1) ? "WHERE " . join(' and ', @WHERE_RULES)  : '';
 
  $self->query($db, "SELECT $date, count(DISTINCT f.uid), count(*),  sum(f.sum), f.uid, u.company_id 
      FROM fees f
      LEFT JOIN users u ON (u.uid=f.uid)
      LEFT JOIN admins a ON (f.aid=a.aid)
      $ext_tables
      $WHERE 
      GROUP BY $GROUP
      ORDER BY $SORT $DESC;");

 my $list = $self->{list}; 

 $self->{SUM}  = '0.00';
 $self->{USERS}= 0; 
if ($self->{TOTAL} > 0 || $PG > 0 ) {	
  $self->query($db, "SELECT count(DISTINCT f.uid), count(*), sum(f.sum) 
      FROM fees f
      LEFT JOIN users u ON (u.uid=f.uid)
      $WHERE;");

  ($self->{USERS}, 
   $self->{TOTAL}, 
   $self->{SUM}) = @{ $self->{list}->[0] };
}
	
	return $list;
}

#**********************************************************
# fees_type_list()
#**********************************************************
sub fees_type_list {
 my $self = shift;
 my ($attr) = @_;


 $SORT = ($attr->{SORT}) ? $attr->{SORT} : 1;
 $DESC = ($attr->{DESC}) ? $attr->{DESC} : '';
 $PG   = ($attr->{PG}) ? $attr->{PG} : 0;
 $PAGE_ROWS = ($attr->{PAGE_ROWS}) ? $attr->{PAGE_ROWS} : 25;

 @WHERE_RULES = ();
 
 if ($attr->{NAME}) {
	 push @WHERE_RULES, @{ $self->search_expr($attr->{NAME}, 'STR', 'name') };
  }

 if ($attr->{ID}) {
	 push @WHERE_RULES, @{ $self->search_expr($attr->{ID}, 'INT', 'id') };
  }

 my $WHERE = ($#WHERE_RULES > -1) ?  "WHERE " . join(' and ', @WHERE_RULES) : ''; 

 $self->query($db, "SELECT id, name, default_describe, sum FROM fees_types
  $WHERE 
  ORDER BY $SORT $DESC
  LIMIT $PG, $PAGE_ROWS;");

 return $self->{list};
}


#**********************************************************
# fees_types_info()
#**********************************************************
sub fees_type_info {
 my $self = shift;
 my ($attr) = @_;
 
 $self->query($db, "select id, name, default_describe, sum FROM fees_types WHERE id='$attr->{ID}';");

 return $self if ($self->{errno} || $self->{TOTAL} < 1);

 ($self->{ID},
 	$self->{NAME},
 	$self->{DEFAULT_DESCRIBE},
 	$self->{SUM}
 	) = @{ $self->{list}->[0] };

 return $self;
}

#**********************************************************
# fees_types_change()
#**********************************************************
sub fees_type_change {
 my $self = shift;
 my ($attr) = @_;

 my %FIELDS = (ID          => 'id',
               NAME        => 'name',
               DEFAULT_DESCRIBE => 'default_describe',
               SUM         => 'sum'
               );

 $self->changes($admin, { CHANGE_PARAM => 'ID',
		               TABLE        => 'fees_types',
		               FIELDS       => \%FIELDS,
		               OLD_INFO     => $self->fees_type_info({ %$attr }),
		               DATA         => $attr
		              } );

 return $self;
}



#**********************************************************
# fees_type_add()
#**********************************************************
sub fees_type_add {
 my $self = shift;
 my ($attr) = @_;

 $self->query($db, "INSERT INTO fees_types (id, name, default_describe, sum) 
  values ('$attr->{ID}', '$attr->{NAME}', '$attr->{DEFAULT_DESCRIBE}', '$attr->{SUM}');", 'do');

 $admin->system_action_add("FEES_TYPES:$self->{INSERT_ID}:$attr->{NAME}", { TYPE => 1 }) if (! $self->{errno});
 return $self;
}


#**********************************************************
# fees_type_del()
#**********************************************************
sub fees_type_del {
 my $self = shift;
 my ($id) = @_;

 $self->query($db, "DELETE FROM fees_types WHERE id='$id';", 'do');

 $admin->system_action_add("FEES_TYPES:$id", { TYPE => 10 }) if (! $self->{errno});
 return $self;
}










1
