#!/usr/bin/perl -w
# Paysys processing system
# Check payments incomming request
#

use vars qw($begin_time %FORM %LANG 
$DATE $TIME
$CHARSET 
@MODULES
$admin
$users 
$payments
$Paysys
$debug
%conf
%PAYSYS_PAYMENTS_METHODS
);

BEGIN {
 my $libpath = '../';
 
 $sql_type='mysql';
 unshift(@INC, $libpath ."Abills/$sql_type/");
 unshift(@INC, $libpath);
 unshift(@INC, $libpath . 'libexec/');
 unshift(@INC, $libpath . 'Abills/modules/Paysys');

 eval { require Time::HiRes; };
 if (! $@) {
    Time::HiRes->import(qw(gettimeofday));
    $begin_time = gettimeofday();
   }
 else {
    $begin_time = 0;
  }
}

require "config.pl";
use Abills::Base;
use Abills::SQL;
use Abills::HTML;
use Users;
use Paysys;
use Finance;
use Admins;

$debug  = $conf{PAYSYS_DEBUG} || 0;

my $html   = Abills::HTML->new();
my $sql    = Abills::SQL->connect($conf{dbtype}, $conf{dbhost}, $conf{dbname}, $conf{dbuser},
    $conf{dbpasswd}, { CHARSET => ($conf{dbcharset}) ? $conf{dbcharset} : undef  });
my $db     = $sql->{db};
#Operation status
my $status = '';

if ($Paysys::VERSION < 3.2) {
	print "Content=-Type: text/html\n\n";
 	print "Please update module 'Paysys' to version 3.2 or higher. http://abills.net.ua/";
 	return 0;
 }


#Check allow ips
if ($conf{PAYSYS_IPS}) {
	$conf{PAYSYS_IPS}=~s/ //g;
	@ips_arr = split(/,/, $conf{PAYSYS_IPS});
	
	#Default DENY FROM all
	my $allow = 0;
	foreach my $ip (@ips_arr) {
		#Deny address
		if ($ip =~ /^!/  && $ip =~ /$ENV{REMOTE_ADDR}$/) {
      last;
		 }
		#allow address
		elsif ($ENV{REMOTE_ADDR} =~ /^$ip/) {
			$allow=1;
			last;
		 }
	  #allow from all networks
	  elsif ($ip eq '0.0.0.0') {
	  	$allow=1;
	  	last;
	   }
	 }

  #Address not allow
  #Send info mail to admin
  if (! $allow) {
  	print "Content-Type: text/html\n\n";
  	print "Error: IP '$ENV{REMOTE_ADDR}' DENY by System";
    sendmail("$conf{ADMIN_MAIL}", "$conf{ADMIN_MAIL}", "ABillS - Paysys", 
              "IP '$ENV{REMOTE_ADDR}' DENY by System", "$conf{MAIL_CHARSET}", "2 (High)");
  	exit;
   } 
}


if ($conf{PAYSYS_PASSWD}) {
	my($user, $password)=split(/:/, $conf{PAYSYS_PASSWD});
	
	if (defined($ENV{HTTP_CGI_AUTHORIZATION})) {
  $ENV{HTTP_CGI_AUTHORIZATION} =~ s/basic\s+//i;
  my ($REMOTE_USER,$REMOTE_PASSWD) = split(/:/, decode_base64($ENV{HTTP_CGI_AUTHORIZATION}));  

#  print "Content-Type: text/html\n\n";
#  print "($REMOTE_PASSWD ne $password || $REMOTE_USER ne $user)";

  if ((! $REMOTE_PASSWD) || ($REMOTE_PASSWD && $REMOTE_PASSWD ne $password) 
    || (! $REMOTE_USER) || ($REMOTE_USER && $REMOTE_USER ne $user)) {
    print "WWW-Authenticate: Basic realm=\"Billing system\"\n";
    print "Status: 401 Unauthorized\n";
    print "Content-Type: text/html\n\n";
    print "Access Deny";
    exit;
   }
  }
}

$Paysys   = Paysys->new($db, undef, \%conf);
$admin = Admins->new($db, \%conf);
$admin->info($conf{SYSTEM_ADMIN_ID}, { IP => $ENV{REMOTE_ADDR} });
$payments = Finance->payments($db, $admin, \%conf);
$users = Users->new($db, $admin, \%conf); 

%PAYSYS_PAYMENTS_METHODS=%{ cfg2hash($conf{PAYSYS_PAYMENTS_METHODS}) };

#debug =========================================
my $output2 = '';
if ($debug > 0) {
  while(my($k, $v)=each %FORM) {
 	  $output2 .= "$k -> $v\n"	if ($k ne '__BUFFER');
  }
  mk_log($output2);
}
#END debug =====================================

my $ip_num   = unpack("N", pack("C4", split( /\./, $ENV{REMOTE_ADDR})));
if ($ip_num >= ip2int('213.186.115.164') && $ip_num <= ip2int('213.186.115.190')) {
  require "Ibox.pm";
	exit;
 }
elsif( $FORM{sender_phone} && $FORM{pay_way}) {
  require "Liqpay.pm";
  liqpay_payments();
	exit;
 }
elsif( $FORM{txn_id} || $FORM{prv_txn} || defined($FORM{prv_id}) || ( $FORM{command} && $FORM{account}  ) ) {
	osmp_payments();
 }
elsif ($FORM{SHOPORDERNUMBER}) {
  portmone_payments();
 }
elsif($FORM{AcqID}) {
	privatbank_payments();
 }
elsif($FORM{operation} || $ENV{'QUERY_STRING'} =~ /operation=/) {
	require "Comepay.pm";
	exit;
 }
elsif ($FORM{'<OPERATION id'} || $FORM{'%3COPERATION%20id'}) {
	require "Express-oplata.pm";
	exit;
 }
elsif($FORM{ACT}) {
	require "24_non_stop.pm";
	exit;
}

#Check payment system by IP

#OSMP
my $first_ip = unpack("N", pack("C4", split( /\./, '79.142.16.0')));
my $mask_ips = unpack("N", pack("C4", split( /\./, '255.255.255.255'))) - unpack("N", pack("C4", split( /\./, '255.255.240.0')));
my $last_ip  = $first_ip + $mask_ips;


if ($ENV{REMOTE_ADDR} =~ /^92\.125\./) {
	osmp_payments_v4();
	exit;
 }
elsif ($ENV{REMOTE_ADDR} =~ /^93\.183\.196\.26$/ || 
       $ENV{REMOTE_ADDR} =~ /^195\.230\.131\.50$/||
       $ENV{REMOTE_ADDR} =~ /^93\.183\.196\.28$/
        ) {
 	require "Easysoft.pm";
 	exit;
 } 
elsif ($ENV{REMOTE_ADDR} =~ /^192.168.1.1/) {
 	require "Erip.pm";
 	exit;
 }
elsif ($ip_num > $first_ip && $ip_num < $last_ip) {
        print "Content-Type: text/xml\n\n";
        print "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
        print "<response>\n";
        print "<result>300</result>\n";
        print "<result1>$ENV{REMOTE_ADDR}</result1>\n";
        print " </response>\n";
        exit;
 } 
#USMP
elsif('77.222.138.142,195.10.218.120' =~ /$ENV{REMOTE_ADDR}/ && ! $conf{PAYSYS_USMP_OLD}) {
  usmp_payments_v2();
  exit;
 }
elsif ($FORM{payment} && $FORM{payment}=~/pay_way/) {
 	require "P24.pm";
 	p24_payments();
 	exit;
 }


print "Content-Type: text/html\n\n";

eval { require Digest::MD5; };
if (! $@) {
   Digest::MD5->import();
  }
else {
   print "Content-Type: text/html\n\n";
   print "Can't load 'Digest::MD5' check http://www.cpan.org";
   exit;
 }

my $md5 = new Digest::MD5;


payments();




#**********************************************************
#
#**********************************************************
sub payments {

  if ($FORM{LMI_PAYMENT_NO}) { # || $FORM{LMI_HASH}) {
  	wm_payments();
   }
  elsif($FORM{rupay_action}) {
  	rupay_payments();
   }
  elsif ($FORM{id_ups}) {
  	ukrpays_payments();
   }
  elsif($FORM{smsid}) {
    smsproxy_payments();
   }
  elsif ($FORM{sign}) {
  	usmp_payments();
   }
  elsif ($FORM{lr_paidto}) {
 		require "Libertyreserve.pm";
   }
  else {
    print "Error: Unknown payment system";
    if (scalar keys %FORM > 0) {
     	if ($debug == 0) {
     	  while(my($k, $v)=each %FORM) {
	        $output2 .= "$k -> $v\n"	if ($k ne '__BUFFER');
        }
       }
    	mk_log($output2);
    }
   }
}

#**********************************************************
#
#**********************************************************
sub portmone_payments {
  #Get order
  my $status = 0;
  my $list = $Paysys->list({ TRANSACTION_ID => "$FORM{'SHOPORDERNUMBER'}", 
      	                     INFO           => '-'
  	                         });




      if ($Paysys->{TOTAL} > 0) {
	      #$html->message('info', $_INFO, "$_ADDED $_SUM: $list->[0][3] ID: $FORM{SHOPORDERNUMBER }");
	      my $uid = $list->[0][8];
	      my $sum = $list->[0][3];
        my $user = $users->info($uid);
        $payments->add($user, {SUM      => $sum,
    	                     DESCRIBE     => 'PORTMONE', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{45}) ? 45 : '2',
  	                       EXT_ID       => "PM:$FORM{SHOPORDERNUMBER}",
  	                       CHECK_EXT_ID => "PM:$FORM{SHOPORDERNUMBER}" } );  


        #Exists
        if ($payments->{errno} && $payments->{errno} == 7) {
          $status = 8;  	
         }
        elsif ($payments->{errno}) {
          $status = 4;
         }
        else {
          $Paysys->change({ ID     => $list->[0][0],
         	                  INFO   => "APPROVALCODE: $FORM{APPROVALCODE}" 
         	                 })  ;
      	  $status = 1;
         }    


        

        

	      if ($conf{PAYSYS_EMAIL_NOTICE}) {
	      	my $message = "\n".
	      	 "System: Portmone\n".
	      	 "DATE: $DATE $TIME\n".
	      	 "LOGIN: $user->{LOGIN} [$uid]\n".
	      	 "\n".
       	   "\n".
	      	 "ID: $FORM{SHOPORDERNUMBER}\n".
	      	 "SUM: $sum\n";

          sendmail("$conf{ADMIN_MAIL}", "$conf{ADMIN_MAIL}", "Paysys Portmone Add", 
              "$message", "$conf{MAIL_CHARSET}", "2 (High)");
	      	
	       }
	     }
	
	#money added sucesfully
	my $home_url = '/index.cgi';
  $home_url = $ENV{SCRIPT_NAME};
  $home_url =~ s/paysys_check.cgi/index.cgi/;
  
	if ($status == 1) {
	  print "Location: $home_url?index=$FORM{index}&sid=$FORM{sid}&SHOPORDERNUMBER=$FORM{SHOPORDERNUMBER}&TRUE=1". "\n\n";
	 }
	else {
		#print "Content-Type: text/html\n\n";
		#print "FAILED PAYSYS: Portmone SUM: $FORM{BILL_AMOUNT} ID: $FORM{SHOPORDERNUMBER} STATUS: $status";
		print "Location: $home_url?index=$FORM{index}&sid=$FORM{sid}&SHOPORDERNUMBER=$FORM{SHOPORDERNUMBER}". "\n\n";
	 }

	exit;
}


#**********************************************************
#MerID=100000000918471  
#OrderID=test00000001g5hg45h45
#AcqID=414963
#Signature=e2DkM6RYyNcn6+okQQX2BNeg/+k=
#ECI=5
#IP=217.117.65.41
#CountryBIN=804
#CountryIP=804
#ONUS=1
#Time=22/01/2007 13:56:38
#Signature2=nv7CcUe5t9vm+uAo9a52ZLHvRv4=
#ReasonCodeDesc=Transaction is approved.
#ResponseCode=1
#ReasonCode=1
#ReferenceNo=702308304646
#PaddedCardNo=XXXXXXXXXXXX3982
#AuthCode=073291
#**********************************************************
sub privatbank_payments {
  #Get order
  my $status = 0;

  my $list = $Paysys->list({ TRANSACTION_ID => "$FORM{'OrderID'}", 
      	                     INFO           => '-',
  	                         });

 if ($Paysys->{TOTAL} > 0) {
   if (	$FORM{ReasonCode} == 1 ) {     
	      #$html->message('info', $_INFO, "$_ADDED $_SUM: $list->[0][3] ID: $FORM{SHOPORDERNUMBER }");
	      my $uid = $list->[0][8];
	      my $sum = $list->[0][3];
        my $user = $users->info($uid);
        $payments->add($user, {SUM      => $sum,
    	                     DESCRIBE     => 'PBANK', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{48}) ? 48 : '2',  
  	                       EXT_ID       => "PBANK:$FORM{OrderID}",
  	                       CHECK_EXT_ID => "PBANK:$FORM{OrderID}" } );  


        #Exists
        if ($payments->{errno} && $payments->{errno} == 7) {
          $status = 8;  	
         }
        elsif ($payments->{errno}) {
          $status = 4;
         }
        else{
   	      $Paysys->change({ ID        => $list->[0][0],
   	      	                PAYSYS_IP => $ENV{'REMOTE_ADDR'},
 	                          INFO      => "ReasonCode: $FORM{ReasonCode}\n Authcode: $FORM{AuthCode}\n PaddedCardNo: $FORM{PaddedCardNo}\n ResponseCode: $FORM{ResponseCode}\n ReasonCodeDesc: $FORM{ReasonCodeDesc}\n IP: $FORM{IP}\n Signature: $FORM{Signature}" 
 	                  });
         }

	      if ($conf{PAYSYS_EMAIL_NOTICE}) {
	      	my $message = "\n".
	      	 "System: Privat Bank\n".
	      	 "DATE: $DATE $TIME\n".
	      	 "LOGIN: $user->{LOGIN} [$uid]\n".
	      	 "\n".
       	   "\n".
	      	 "ID: $list->[0][0]\n".
	      	 "SUM: $sum\n";

          sendmail("$conf{ADMIN_MAIL}", "$conf{ADMIN_MAIL}", "Privat Bank Add", 
              "$message", "$conf{MAIL_CHARSET}", "2 (High)");
	      	
	       }

    }
   else {
     $Paysys->change({ ID        => $list->[0][0],
     	                 PAYSYS_IP => $ENV{'REMOTE_ADDR'},
 	                     INFO      => "ReasonCode: $FORM{ReasonCode}. $FORM{ReasonCodeDesc}" 
 	                 });
  	}

  }
	
  
	my $home_url = '/index.cgi';
  $home_url = $ENV{SCRIPT_NAME};
  $home_url =~ s/paysys_check.cgi/index.cgi/;
  
	if ($FORM{ResponseCode} == 1) {
	  print "Location: $home_url?PAYMENT_SYSTEM=48&OrderID=$FORM{OrderID}&TRUE=1". "\n\n";
	 }
	else {
		#print "Content-Type: text/html\n\n";
		#print "FAILED PAYSYS: Portmone SUM: $FORM{BILL_AMOUNT} ID: $FORM{SHOPORDERNUMBER} STATUS: $status";
		print "Location: $home_url?PAYMENT_SYSTEM=48&OrderID=$FORM{OrderID}&FALSE=1&ReasonCodeDesc=$FORM{ReasonCodeDesc}&ReasonCode=$FORM{ReasonCode}&ResponseCode=$FORM{ResponseCode}". "\n\n";
	 }


	exit;
}

#**********************************************************
# OSMP / Pegas
#**********************************************************
sub osmp_payments {

 if ($conf{PAYSYS_PEGAS_PASSWD}) {
   my($user, $password)=split(/:/, $conf{PAYSYS_PEGAS_PASSWD});
	
	if (defined($ENV{HTTP_CGI_AUTHORIZATION})) {
  $ENV{HTTP_CGI_AUTHORIZATION} =~ s/basic\s+//i;
  my ($REMOTE_USER,$REMOTE_PASSWD) = split(/:/, decode_base64($ENV{HTTP_CGI_AUTHORIZATION}));  
  if ((! $REMOTE_PASSWD) || ($REMOTE_PASSWD && $REMOTE_PASSWD ne $password) 
    || (! $REMOTE_USER) || ($REMOTE_USER && $REMOTE_USER ne $user)) {
    print "WWW-Authenticate: Basic realm=\"Billing system\"\n";
    print "Status: 401 Unauthorized\n";
    print "Content-Type: text/html\n\n";
    print "Access Deny";
    exit;
   }
  }
 }

 print "Content-Type: text/xml\n\n";
 my $txn_id            = 'osmp_txn_id';
 my $payment_system    = 'OSMP';
 my $payment_system_id = 44;
 my $CHECK_FIELD = $conf{PAYSYS_OSMP_ACCOUNT_KEY} || 'UID';

my %status_hash = (0	=> 'Success',
  1   => 'Temporary DB error',
  4	  => 'Wrong client indentifier',
  5	  => 'Failed witness a signature',
  6	  => 'Unknown terminal',
  7	  => 'Payments deny',
  
  8	  => 'Double request',
  9	  => 'Key Info mismatch',
  79  => 'Счёт абонента не активен',
  300	=> 'Unknown error',
  );

 #For pegas
 if ($conf{PAYSYS_PEGAS}) {
 	 $txn_id            = 'txn_id';
 	 $payment_system    = 'PEGAS';
 	 $payment_system_id = 49;
 	 $status_hash{5}    = 'Неверный индентификатор абонента';
 	 $status_hash{243}  = 'Невозможно проверитьсостояние счёта';
 	 $CHECK_FIELD       = $conf{PAYSYS_PEGAS_ACCOUNT_KEY} || 'UID';
  }

my $comments = '';
my $command = $FORM{command};
$FORM{account} =~ s/^0+//g if ($FORM{account});
my %RESULT_HASH=( result => 300 );
my $results = '';

mk_log("$payment_system: $ENV{QUERY_STRING}") if ($debug > 0);

#Check user account
#https://service.someprovider.ru:8443/payment_app.cgi?command=check&txn_id=1234567&account=0957835959&sum=10.45
if ($command eq 'check') {
  my $list = $users->list({ $CHECK_FIELD => $FORM{account} });

  if (! $conf{PAYSYS_PEGAS} && ! $FORM{sum}) {
  	$status = 300; 
   }
  elsif ($users->{errno}) {
	  $status = 300; 
   }
  elsif ($users->{TOTAL} < 1) {
	  if ($CHECK_FIELD eq 'UID' && $FORM{account} !~ /\d+/) {
	    $status   =  4;
	   }
	  else {
	  	$status   =  5;
	   }
	  $comments = 'User Not Exist';
   }
  else {
    $status = 0; 
   }

$RESULT_HASH{result} = $status;

#For OSMP
if ($payment_system_id == 44) {
  $RESULT_HASH{$txn_id}= $FORM{txn_id} ;
  $RESULT_HASH{prv_txn}= $FORM{prv_txn};
  $RESULT_HASH{comment}= "Balance: $list->[0]->[2]" if ($status == 0);
 }
}
#Cancel payments
elsif ($command eq 'cancel') {
  my $prv_txn = $FORM{prv_txn};
  $RESULT_HASH{prv_txn}=$prv_txn;

  my $list = $payments->list({ ID => "$prv_txn", EXT_ID => "PEGAS:*"  });

  if ($payments->{errno}) {
      $RESULT_HASH{result}=1;
   }
  elsif ($payments->{TOTAL} < 1) {
  	if ($conf{PAYSYS_PEGAS})  {
  		$RESULT_HASH{result}=0;
  	 }
  	else {
  	  $RESULT_HASH{result}=79;
  	 }
   }
  else {
	  my %user = (
     BILL_DI => $list->[10],
     UID     => $list->[11]
    );

  	$payments->del(\%user, $prv_txn);
    if (! $payments->{errno}) {
      $RESULT_HASH{result}=0;
     }
    else {
      $RESULT_HASH{result}=1;
     }
   }
 }
elsif ($command eq 'balance') {
  	
 }
#https://service.someprovider.ru:8443/payment_app.cgi?command=pay&txn_id=1234567&txn_date=20050815120133&account=0957835959&sum=10.45
elsif ($command eq 'pay') {
  my $user;
  my $payments_id = 0;

  if ($CHECK_FIELD eq 'UID') {
    $user = $users->info($FORM{account});
   }
  else {
    my $list = $users->list({ $CHECK_FIELD => $FORM{account} });

    if (! $users->{errno} && $users->{TOTAL} > 0 ) {

      my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
      $user = $users->info($uid); 
     }
   }

  if ($users->{errno}) {
    $status = ($users->{errno} == 2) ? 5 : 300;
   }
  elsif ($users->{TOTAL} < 1) {
	  $status =  4;
   }
  elsif (! $FORM{sum}) {
	  $status =  300;
   }
  else {
    #Add payments
    $payments->add($user, {SUM          => $FORM{sum},
    	                     DESCRIBE     => "$payment_system", 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{44}) ? 44 : '2', , 
  	                       EXT_ID       => "$payment_system:$FORM{txn_id}",
  	                       CHECK_EXT_ID => "$payment_system:$FORM{txn_id}" } );  


    #Exists
    if ($payments->{errno} && $payments->{errno} == 7) {
      $status      = 0;  	
      $payments_id = $payments->{ID};
     }
    elsif ($payments->{errno}) {
      $status = 4;
     }
    else {
    	$status = 0;
    	$Paysys->add({ SYSTEM_ID   => $payment_system_id, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$FORM{sum}",
  	            UID            => "$user->{UID}", 
                IP             => '0.0.0.0',
                TRANSACTION_ID => "$payment_system:$FORM{txn_id}",
                INFO           => "TYPE: $FORM{command} PS_TIME: ".
  (($FORM{txn_date}) ? $FORM{txn_date} : '' ) ." STATUS: $status $status_hash{$status}",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

      $payments_id = ($Paysys->{INSERT_ID}) ? $Paysys->{INSERT_ID} : 0;
     }    


	 }

$RESULT_HASH{result} = $status;
$RESULT_HASH{$txn_id}= $FORM{txn_id};
$RESULT_HASH{prv_txn}= $payments_id;
$RESULT_HASH{sum}    = $FORM{sum};
}

#Result output
$RESULT_HASH{comment}=$status_hash{$RESULT_HASH{result}} if ($RESULT_HASH{result} && ! $RESULT_HASH{comment});

while(my($k, $v) = each %RESULT_HASH) {
	$results .= "<$k>$v</$k>\n";
}

print << "[END]";
<?xml version="1.0" encoding="UTF-8"?> 
<response>
$results
</response> 
[END]

exit;
}

#**********************************************************
# OSMP 
# protocol-version 4.00
# IP 92.125.xxx.xxx
# $conf{PAYSYS_OSMP_LOGIN}
# $conf{PAYSYS_OSMP_PASSWD}
# $conf{PAYSYS_OSMP_SERVICE_ID}
# $conf{PAYSYS_OSMP_TERMINAL_ID}
#
#**********************************************************
sub osmp_payments_v4 {
 my $version = '0.2';
 $debug      =  1;

 print "Content-Type: text/xml\n\n";
 
 #my $payment_system    = 'OSMP';
 #my $payment_system_id = 44;
 my $payment_system    = 'OSMP';
 my $payment_system_id = 61;
 my $CHECK_FIELD = $conf{PAYSYS_OSMP_ACCOUNT_KEY} || 'UID';
 $FORM{__BUFFER}='' if (! $FORM{__BUFFER});
 $FORM{__BUFFER}=~s/data=//;

#
#$FORM{__BUFFER}=qq{<?xml version="1.0" encoding="UTF-8"?><request>
#<protocol-version>4.00</protocol-version><request-type>10</request-type><terminal-id>1</terminal-id>
#<extra name="login">login</extra><extra name="password-md5">1a1dc91c907325c69271ddf0c944bc72</extra>
#<extra name="client-software">Dealer v0</extra><auth count="1" to-amount="1.00"><payment>
#<transaction-number>155</transaction-number><from><amount>1.00</amount></from><to><amount>1.00</amount>
#<service-id>1</service-id><account-number>234456</account-number></to><receipt><datetime>20100407155326</datetime>
#<receipt-number>407155313</receipt-number></receipt></payment></auth></request>
#};

eval { require XML::Simple; };
if (! $@) {
   XML::Simple->import();
 }
else {
   print "Content-Type: text/html\n\n";
   print "Can't load 'XML::Simple' check http://www.cpan.org";
   exit;
 }

$FORM{__BUFFER} =~ s/encoding="windows-1251"//g;
my $_xml = eval { XMLin("$FORM{__BUFFER}", forcearray=>1) };

if($@) {
  mk_log("---- Content:\n".
      $FORM{__BUFFER}.
      "\n----XML Error:\n".
      $@
      ."\n----\n");

  return 0;
}
else {
  if ($debug == 1) {
 	  mk_log($FORM{__BUFFER});
   }
}



my %request_hash = ();
my $request_type = '';

my $status_id    = 0;
my $result_code  = 0;
my $service_id   = 0;
my $response     = '';

my $BALANCE      = 0.00;
my $OVERDRAFT    = 0.00;
my $txn_date     = "$DATE$TIME";
$txn_date =~ s/[-:]//g;
my $txn_id = 0;

$request_hash{'protocol-version'}   =  $_xml->{'protocol-version'}->[0];
$request_hash{'request-type'}       =  $_xml->{'request-type'}->[0] || 0;
$request_hash{'terminal-id'}        =  $_xml->{'terminal-id'}->[0];
$request_hash{'login'}              =  $_xml->{'extra'}->{'login'}->{'content'};
$request_hash{'password'}           =  $_xml->{'extra'}->{'password'}->{'content'};
$request_hash{'password-md5'}       =  $_xml->{'extra'}->{'password-md5'}->{'content'};
$request_hash{'client-software'}    =  $_xml->{'extra'}->{'client-software'}->{'content'};

my $transaction_number              =  $_xml->{'transaction-number'}->[0] || '';

$request_hash{'to'} = $_xml->{to};

if ($conf{PAYSYS_OSMP_LOGIN} ne $request_hash{'login'} || 
 ($request_hash{'password'} && $conf{PAYSYS_OSMP_PASSWD} ne $request_hash{'password'})) {
	$status_id    = 150;
	$result_code  = 1;


  $response = qq{
<txn-date>$txn_date</txn-date>
<status-id>$status_id</status-id>
<txn-id>$txn_id</txn-id>
<result-code>$result_code</result-code>
};	
 }
elsif (defined($_xml->{'status'})) {
	my $count = $_xml->{'status'}->[0]->{count};
  my @payments_arr=();
  my %payments_status = ();
  
  for(my $i=0; $i<$count; $i++) {
  	push @payments_arr, $_xml->{'status'}->[0]->{'payment'}->[$i]->{'transaction-number'}->[0];
   }  

  my $ext_ids = "'$payment_system:". join("', '$payment_system:", @payments_arr)."'";
  my $list = $payments->list({ EXT_IDS => $ext_ids, PAGE_ROWS => 100000  });

  if ($payments->{errno}) {
     $status_id=78;
   }
  else {
    foreach my $line (@$list) {
  	  my $ext = $line->[7];
  	  $ext =~ s/$payment_system://g;
  	  $payments_status{$ext}=$line->[0];
     }

    foreach my $id (@payments_arr) {
      if ($id < 1) {
    	  $status_id=160;
       }
      elsif ($payments_status{$id}) {
    	  $status_id=60;
       }          
      else {
        $status_id=10;
       }

      $response .= qq{ 
<payment transaction-number="$id" status="$status_id" result-code="0" final-status="true" fatal-error="true">
</payment>\n };
     }	
   }
 }
#User info
elsif ($request_hash{'request-type'} == 1) {
  my $to             = $request_hash{'to'}->[0];
  my $amount         = $to->{'amount'}->[0];
  my $sum            = $amount->{'content'};
  my $currency       = $amount->{'currency-code'};
  my $account_number = $to->{'account-number'}->[0];
  my $service_id     = $to->{'service-id'}->[0];
  my $receipt_number = $_xml->{receipt}->[0]->{'receipt-number'}->[0];

  my $user;
  my $payments_id = 0;
  
  if ($CHECK_FIELD eq 'UID') {
    $user = $users->info($account_number);
    $BALANCE      = sprintf("%2.f", $user->{DEPOSIT});
    $OVERDRAFT    = $user->{CREDIT};
   }
  else {
    my $list = $users->list({ $CHECK_FIELD => $account_number });

    if (! $users->{errno} && $users->{TOTAL} > 0 ) {
      my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
      $user = $users->info($uid);
      $BALANCE      = sprintf("%2.f", $user->{DEPOSIT});
      $OVERDRAFT    = $user->{CREDIT};
     }
   }

  if ($users->{errno}) {
	  $status_id   =  79;
	  $result_code =  1;
   }
  elsif ($users->{TOTAL} < 1) {
	  $status_id   =  5;
	  $result_code =  1;
   }


$response = qq{
<txn-date>$txn_date</txn-date>
<status-id>$status_id</status-id>
<txn-id>$txn_id</txn-id>
<result-code>$result_code</result-code>
<from>
<service-id>$service_id</service-id>
<account-number>$account_number</account-number>
</from>
<to>
<service-id>1</service-id>
<amount>amount</amount>
<account-number>$account_number</account-number>
<extra name="FIO">$user->{FIO}</extra>
</to>};
}
# Payments
elsif($request_hash{'request-type'} == 2) {
  my $to             = $request_hash{'to'}->[0];
  my $amount         = $to->{'amount'}->[0];
  my $sum            = $amount->{'content'};
  my $currency       = $amount->{'currency-code'};
  my $account_number = $to->{'account-number'}->[0];
  my $service_id     = $to->{'service-id'}->[0];
  my $receipt_number = $_xml->{receipt}->[0]->{'receipt-number'}->[0];
  
  my $txn_id = 0;
  my $user;
  my $payments_id = 0;

  if ($CHECK_FIELD eq 'UID') {
    $user = $users->info($account_number);
    $BALANCE      = sprintf("%2.f", $user->{DEPOSIT});
    $OVERDRAFT    = $user->{CREDIT};
   }
  else {
    my $list = $users->list({ $CHECK_FIELD => $account_number });

    if (! $users->{errno} && $users->{TOTAL} > 0 ) {
      my $uid     = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
      $user       = $users->info($uid);
      $BALANCE    = sprintf("%2.f", $user->{DEPOSIT});
      $OVERDRAFT  = $user->{CREDIT};
     }
   }

  if ($users->{errno}) {
	  $status_id   =  79;
	  $result_code =  1;
   }
  elsif ($users->{TOTAL} < 1) {
	  $status_id   =  5;
	  $result_code =  1;
   }
  else {
    #Add payments
    $payments->add($user, {SUM          => $sum,
    	                     DESCRIBE     => "$payment_system", 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{44}) ? 44 : '2',  
  	                       EXT_ID       => "$payment_system:$transaction_number",
  	                       CHECK_EXT_ID => "$payment_system:$transaction_number" } );  

    #Exists
    if ($payments->{errno} && $payments->{errno} == 7) {
      $status_id   = 10;  	
      $result_code =  1;
      $payments_id = $payments->{ID};
     }
    elsif ($payments->{errno}) {
      $status_id = 78;
      $result_code =  1;
     }
    else {
    	$Paysys->add({ SYSTEM_ID => $payment_system_id, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$sum",
  	            UID            => "$user->{UID}", 
                IP             => '0.0.0.0',
                TRANSACTION_ID => "$payment_system:$transaction_number",
                INFO           => " STATUS: $status_id RECEIPT Number: $receipt_number",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

      $payments_id = ($Paysys->{INSERT_ID}) ? $Paysys->{INSERT_ID} : 0;
      $txn_id = $payments_id;
     }    
	 }

$response = qq{
<txn-date>$txn_date</txn-date>
<txn-id>$txn_id</txn-id>
<receipt>
<datetime>0</datetime>
</receipt>
<from>
<service-id>$service_id</service-id>
<amount>$sum</amount>
<account-number>$account_number</account-number>
</from>
<to>
<service-id>$service_id</service-id>
<amount>$sum</amount>
<account-number>$account_number</account-number>
</to>
}
}
# Pack processing
elsif($request_hash{'request-type'} == 10) {
	my $count = $_xml->{auth}->[0]->{count};
  my $final_status='';
  my $fatal_error='';
	
	for($i=0; $i < $count; $i++) {
    my %request_hash = %{ $_xml->{auth}->[0]->{payment}->[$i] };
    my $to             = $request_hash{'to'}->[0];
    $transaction_number = $request_hash{'transaction-number'}->[0] || '';
#    my $amount         = $to->{'amount'}->[0];
    my $sum            = $to->{'amount'}->[0];
#    my $currency       = $amount->{'currency-code'};
    my $account_number = $to->{'account-number'}->[0];
    my $service_id     = $to->{'service-id'}->[0];
    my $receipt_number = $_xml->{receipt}->[0]->{'receipt-number'}->[0];

  if ($CHECK_FIELD eq 'UID') {
    $user       = $users->info($account_number);
    $BALANCE    = sprintf("%2.f", $user->{DEPOSIT});
    $OVERDRAFT  = $user->{CREDIT};
   }
  else {
    my $list = $users->list({ $CHECK_FIELD => $account_number });

    if (! $users->{errno} && $users->{TOTAL} > 0 ) {
      my $uid    = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
      $user      = $users->info($uid);
      $BALANCE   = sprintf("%2.f", $user->{DEPOSIT});
      $OVERDRAFT = $user->{CREDIT};
     }
   }

  if ($users->{errno}) {
	  $status_id   =  79;
	  $result_code =  1;
   }
  elsif ($users->{TOTAL} < 1) {
	  $status_id   =  0;
	  $result_code =  0;
   }
  else {
    #Add payments
    $payments->add($user, {SUM          => $sum,
    	                     DESCRIBE     => "$payment_system", 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{44}) ? 44 : '2',  
  	                       EXT_ID       => "$payment_system:$transaction_number",
  	                       CHECK_EXT_ID => "$payment_system:$transaction_number" } );  

    #Exists
    if ($payments->{errno} && $payments->{errno} == 7) {
      $status_id   = 10;  	
      $result_code =  1;
      $payments_id = $payments->{ID};
     }
    elsif ($payments->{errno}) {
      $status_id   = 78;
      $result_code =  1;
     }
    else {
    	$Paysys->add({ SYSTEM_ID   => $payment_system_id, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$sum",
  	            UID            => "$user->{UID}", 
                IP             => '0.0.0.0',
                TRANSACTION_ID => "$payment_system:$transaction_number",
                INFO           => " STATUS: $status_id RECEIPT Number: $receipt_number",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

      $payments_id = ($Paysys->{INSERT_ID}) ? $Paysys->{INSERT_ID} : 0;
      $txn_id = $payments_id;
      $status_id = 51;
     }    
	 }

   $fatal_error = ($status_id != 51 && $status_id != 0) ? 'true' : 'false';
$response .= qq{
<payment status="$status_id" transaction-number="$transaction_number" result-code="$result_code" final-status="true" fatal-error="$fatal_error">
<to>
<service-id>$service_id</service-id>
<amount>$sum</amount>
<account-number>$account_number</account-number>
</to>
</payment>
	
};

}
}

my $output = qq{<?xml version="1.0" encoding="windows-1251"?>
<response requestTimeout="60">
<protocol-version>4.00</protocol-version>
<configuration-id>0</configuration-id>
<request-type>$request_hash{'request-type'}</request-type>
<terminal-id>$request_hash{'terminal-id'}</terminal-id>
<transaction-number>$transaction_number</transaction-number>
<status-id>$status_id</status-id>
};

$output .= $response . qq{
 <operator-id>$admin->{AID}</operator-id>
 <extra name="REMOTE_ADDR">$ENV{REMOTE_ADDR}</extra>
 <extra name="client-software">ABillS Paysys $payment_system $version</extra>
 <extra name="version-conf">$version</extra>
 <extra name="serial">$version</extra>
 <extra name="BALANCE">$BALANCE</extra>
 <extra name="OVERDRAFT">$OVERDRAFT</extra>
</response>};

print $output;

if ($debug > 0) {
 	mk_log("RESPONSE:\n". $output);
 }


return $status_id;
}



#**********************************************************
# http://usmp.com.ua/
# Example:
# new version
#
#**********************************************************
sub usmp_payments_v2 {


eval { require XML::Simple; };
if (! $@) {
   XML::Simple->import();
 }
else {
   print "Content-Type: text/html\n\n";
   print "Can't load 'XML::Simple' check http://www.cpan.org";
   exit;
 }

$FORM{__BUFFER}='' if (! $FORM{__BUFFER});
$FORM{__BUFFER}=~s/data=//;

#$FORM{__BUFFER}=qq{<?xml version="1.0" encoding="utf-8"?>
#<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
#<soap:Body>
#<ProcessPayment xmlns="http://usmp.com.ua/">
#<request>
#<Serial>Serial1</Serial>
#<KeyWord>KeyWord</KeyWord>
#<Payments>
#<PaymentDetails>
#<Date>2010-08-09T15:24:42.000000+03:00</Date>
#<PayElementID>100</PayElementID>
#<Account>test</Account>
#<Amount>150</Amount>
#<ChequeNumber>12</ChequeNumber>
#</PaymentDetails>
#</Payments>
#</request>
#</ProcessPayment>
#</soap:Body>
#</soap:Envelope>
#};


my $_xml = eval { XMLin("$FORM{__BUFFER}", forcearray=>1) };

if($@) {
	print "Content-Type: text/xml\n\n";
  usmp_error_msg('212', 'Incorrect XML', { RESPONSE => $request_type,
  	                                       RESULT   => $request_type  });

	my $content = $FORM{__BUFFER};
  open(FILE, ">>paysys_xml.log") or die "Can't open file 'paysys_xml.log' $!\n";
    print FILE "----\n";
    print FILE $content;
    print FILE "\n----\n";
    print FILE $@;
    print FILE "\n----\n";
  close(FILE);

  return 0;

  #print "Content-Type: text/plain\n\n";
  #print "\n$FORM{__BUFFER}\n";
  #print $@;
}

my %request_hash = ();
my $request_type = '';

while(my ($k, $v) = each %{ $_xml->{'soap:Body'}->[0] }) {
	$request_type = $k;
}



if($debug > 0) {
  print "Conten-Type: text/plain\n\n";
  print "\n-- $request_type --\n";
}

my $CHECK_FIELD = $conf{PAYSYS_USMP_ACCOUNT_KEY} || 'UID';

my $id    = 0;  
my $accid = ''; 
my $sum   = 0;  
my $date  = ''; 
my $ChequeNumber = '';

$request_hash{'KeyWord'} = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{KeyWord}->[0];
$request_hash{'Serial'}  = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{Serial}->[0];
my $err_code = 0;
my $type     = '';
print "Content-Type: text/xml\n\n";

$conf{PAYSYS_USMP_MINSUM} = (! $conf{PAYSYS_USMP_MINSUM}) ? 100 : $conf{PAYSYS_USMP_MINSUM} * 100;
$conf{PAYSYS_USMP_MAXSUM} = (! $conf{PAYSYS_USMP_MAXSUM}) ? 100000 : $conf{PAYSYS_USMP_MAXSUM} * 100;

#if ($conf{'PAYSYS_USMP_PAYELEMENTID'} && $request_hash{'PayElementID'} ne $conf{'PAYSYS_USMP_PAYELEMENTID'}  ){
#    usmp_error_msg('121', 'Incorect PayElementID');
#    return 0;
# }

if (! $request_hash{'Serial'} || ! $request_hash{'KeyWord'}) {
  usmp_error_msg('212', 'Incorrect XML', { RESPONSE => $request_type,
  	                                       RESULT   => $request_type  });
  return 0;
 }
elsif ($request_hash{'Serial'} ne $conf{'PAYSYS_USMP_SERIAL'}){
  usmp_error_msg('211', 'IncorrectSerial', { RESPONSE => $request_type,
 	                                           RESULT   => $request_type  });
  return 0;
 }
elsif($request_hash{'KeyWord'} ne $conf{'PAYSYS_USMP_KEYWORD'}) {
  usmp_error_msg('210', 'IncorrectKeyWord', { RESPONSE => $request_type,
  	                                          RESULT   => $request_type  });
  return 0;
 }
#add money
elsif($request_type eq 'ProcessPayment') {
  $type = 'ProcessPaymentsResponse';
  my @result_arr = ();
  my $user;
  my @payments_arr = @{ $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{Payments}->[0]->{PaymentDetails} };

  for(my $i=0; $i<=$#payments_arr; $i++) {
    my $id           = $payments_arr[$i]->{ChequeNumber}->[0];
    my $accid        = $payments_arr[$i]->{Account}->[0];
    my $amount       = $payments_arr[$i]->{Amount}->[0];
    my $sum          = $payments_arr[$i]->{Amount}->[0] / 100;
    my $date         = $payments_arr[$i]->{Date}->[0];
    my $PayElementID = $payments_arr[$i]->{PayElementID}->[0];
  
    $result_arr[$i]{ChequeNumber}= $id;
    $result_arr[$i]{Status}      = 0;
    if ($conf{'PAYSYS_USMP_PAYELEMENTID'}){
    	$conf{'PAYSYS_USMP_PAYELEMENTID'} =~ s/ //g;
    	my @PAYSYS_USMP_PAYELEMENTID_ARR = split(/,/, $conf{'PAYSYS_USMP_PAYELEMENTID'});
    	if (! in_array($PayElementID, \@PAYSYS_USMP_PAYELEMENTID_ARR)) {
        $result_arr[$i]{Status}=121;
       }
     }

  
  if ($amount <= 0){
    $result_arr[$i]{Status}=112;
   }
  elsif ($amount < $conf{PAYSYS_USMP_MINSUM}){
    $result_arr[$i]{Status}=6;
   }
  elsif ($amount > $conf{PAYSYS_USMP_MAXSUM}) {
    $result_arr[$i]{Status}=112;
   }
  elsif ($id < 1) {
    $result_arr[$i]{Status}=120;
   }
  else {
    #Check user account
    my $list = $users->list({ $CHECK_FIELD => $accid });

    if ($users->{errno}) {
      $result_arr[$i]{Status}=113;
     }
    elsif ($users->{TOTAL} < 1) {
      $result_arr[$i]{Status}=113;
     }
    else {
      my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
	    $user = $users->info($uid); 
     }
   }


  if ($result_arr[$i]{Status} < 1) {    
	   $payments->add($user, {SUM         => $sum,
     	                     DESCRIBE     => 'USMP', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{47}) ? 47 : '2',, 
    	                     EXT_ID       => "USMP:$id",
  	                       CHECK_EXT_ID => "USMP:$id" } );  
     
     if ($payments->{errno} && $payments->{errno} == 7) {
       $result_arr[$i]{Status}=108;
      }
     elsif ($payments->{errno}) {
       $result_arr[$i]{Status}=108;
      }  
     else {
       $result_arr[$i]{Status}=9;
      }
    }

  $Paysys->add({ SYSTEM_ID   => 47, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$sum",
  	            UID            => "$accid", 
                IP             => '0.0.0.0',
                TRANSACTION_ID => "USMP:$id",
                INFO           => "STATUS: $result_arr[$i]{Status} ID: $id Account: $accid SUM: $sum DATE: $date  PE: $PayElementID",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

  }


print << "[END]";
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <ProcessPaymentResponse xmlns="http://usmp.com.ua/">
      <ProcessPaymentResult xsi:type="ProcessPaymentsResponse">
        <Statuses>
[END]

for(my $i=0; $i<=$#result_arr; $i++) {

print "    
    <PaymentStatusDetails>
            <ChequeNumber>$result_arr[$i]{ChequeNumber}</ChequeNumber>
            <Status>$result_arr[$i]{Status}</Status>
    </PaymentStatusDetails>
";

 }


print << "[END]";
        </Statuses>
      </ProcessPaymentResult>
    </ProcessPaymentResponse>
  </soap:Body>
</soap:Envelope>
[END]
 }
#Get payments statua   
elsif($request_type eq 'GetStatus') {
  my @payments_arr = @{ $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{ChequeNumbers}->[0]->{int} };
  my %payments_status = ();

    if ($conf{'PAYSYS_USMP_PAYELEMENTID'}){
    	$conf{'PAYSYS_USMP_PAYELEMENTID'} =~ s/ //g;
    	my @PAYSYS_USMP_PAYELEMENTID_ARR = split(/,/, $conf{'PAYSYS_USMP_PAYELEMENTID'});
    	my $PayElementID = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{PayElementID}->[0];
    	if (! in_array($PayElementID, \@PAYSYS_USMP_PAYELEMENTID_ARR)) {
        $payments_status{$id}=121
       }
     }
  
  my $ext_ids = '\'USMP:'. join("', 'USMP:", @payments_arr)."'";
  my $list = $payments->list({ EXT_IDS => $ext_ids, PAGE_ROWS=>10000  });
  

  if ($payments->{errno}) {
     usmp_error_msg('108', "Payments error", { RESPONSE => $request_type,
  	                                           RESULT   => $request_type  });
   }

  foreach my $line (@$list) {
  	my $ext = $line->[7];
  	$ext =~ s/USMP://g;
  	$payments_status{$ext}=$line->[0];
   }  

print << "[END]";
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <GetStatusResponse xmlns="http://usmp.com.ua/">
      <GetStatusResult xsi:type="StatusesResponse">
        <Statuses>
 
[END]

  foreach my $id (@payments_arr) {
    print "<PaymentStatusDetails> \n <ChequeNumber>$id</ChequeNumber>\n
            <Status>"; 
 
    if ($id < 1) {
    	print 120;
     }
    elsif ($payments_status{$id} && $payments_status{$id} == 121) {
    	print 121;
     }          
    else {
      print (($payments_status{$id}) ? 9 : 123 );
     }
    print "</Status>\n</PaymentStatusDetails>\n";
   }

print << "[END]";
        </Statuses>
      </GetStatusResult>
    </GetStatusResponse>
  </soap:Body>
</soap:Envelope>
[END]
 }
#Check limit
elsif($request_type eq 'GetLimit') {
	
  if ($conf{'PAYSYS_USMP_PAYELEMENTID'}){
    my $PayElementID = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{PayElementID}->[0];
    if (! usmp_PayElementID_check($PayElementID, { Account => $accid  })) {
    	  return 0;
     }
   }

	
	my $list = $users->list({ $CHECK_FIELD => $accid });

  my $user ;
  if ($users->{errno}) {
    usmp_error_msg('113', "Can't  find account", { RESPONSE => $request_type,
  	                                               RESULT   => $request_type  });
    return 0;
   }
  elsif ($users->{TOTAL} < 1) {
    usmp_error_msg('113', "Can't  find account", { RESPONSE => $request_type,
  	                                               RESULT   => $request_type  });
    return 0;
   }
  else {
    my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
	  $user = $users->info($uid); 
   }

  my $deposit = int($user->{DEPOSIT}*100);

print << "[END]";
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <GetLimitResponse xmlns="http://usmp.com.ua/">
      <GetLimitResult xsi:type="LimitResponse">
        <Limit>$deposit</Limit>
      </GetLimitResult>
    </GetLimitResponse>
  </soap:Body>
</soap:Envelope>
[END]
}
#Check account
elsif($request_type eq 'ValidatePhone') {
  $accid = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{Account}->[0];
  
 if ($conf{'PAYSYS_USMP_PAYELEMENTID'}){
   my $PayElementID = $_xml->{'soap:Body'}->[0]->{$request_type}->[0]->{request}->[0]->{PayElementID}->[0];
   if (! usmp_PayElementID_check($PayElementID, { Account => $accid })) {
   	  return 0;
    }
  }
	
	
	if ($accid eq '') {
    usmp_error_msg('113', "Can't  find account", { RESPONSE => $request_type,
  	                                               RESULT   => $request_type  });
    return 0;
   }

	
	my $list = $users->list({ $CHECK_FIELD => "$accid" });
  my $login = '';
  my $user ;
  my $status = undef;
  if ($users->{errno}) {
    $status = 113;
   }
  elsif ($users->{TOTAL} < 1) {
    $status =  113;
   }
  else {
    my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
	  $user = $users->info($uid); 
   }

  my $result = ($user->{DISABLE}) ? 'false' : 'true';

print << "[END]";	
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <ValidatePhoneResponse xmlns="http://usmp.com.ua/">
      <ValidatePhoneResult xsi:type="ValidatePhoneResponse">
        <Account>$accid</Account>
        
[END]

if ($status) {
	print "<Result>false</Result>\n";

}
else {
	print "<Result>$result</Result>\n";
}

print << "[END]";	
        <Message>$user->{LOGIN} DEPOSIT: $user->{DEPOSIT}</Message>
      </ValidatePhoneResult>
    </ValidatePhoneResponse>
  </soap:Body>
</soap:Envelope>
[END]
}
else {
	
}

}


#**********************************************************
#
#**********************************************************
sub usmp_PayElementID_check () {
	my ($PayElementID, $attr) = @_;
	
	
  $conf{'PAYSYS_USMP_PAYELEMENTID'} =~ s/ //g;
  my @PAYSYS_USMP_PAYELEMENTID_ARR = split(/,/, $conf{'PAYSYS_USMP_PAYELEMENTID'});
  if (! in_array($PayElementID, \@PAYSYS_USMP_PAYELEMENTID_ARR)) {

print << "[END]";  
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<soap:Body>
<ValidatePhoneResponse xmlns="http://usmp.com.ua/">
<ValidatePhoneResult xsi:type="ValidatePhoneResponse">
<Result>false</Result>
[END]

while(my($k, $v)=each %$attr) {
	print "<$k>$v</$k>\n";
	
}

print << "[END]";  
</ValidatePhoneResult>
</ValidatePhoneResponse>
</soap:Body>
</soap:Envelope>
[END]
  return 0;
   }
	
	return 1;
}

#**********************************************************
#
#**********************************************************
sub usmp_error_msg {
  my ($code, $message, $attr) = @_;

  my $type_response = ($attr->{RESPONSE}) ? $attr->{RESPONSE}.'Response': 'GetStatusResponse';
  my $type_result   = ($attr->{RESULT}) ?  $attr->{RESULT}.'Result': 'GetStatusResult';
  
print << "[END]";
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <$type_response xmlns="http://usmp.com.ua/">
      <$type_result xsi:type="ErrorMessageResponse">
        <ErrorCode>$code</ErrorCode>
        <ErrorMessage>$message</ErrorMessage>
      </$type_result>
    </$type_response>
  </soap:Body>
</soap:Envelope>
[END]
}




#**********************************************************
# http://usmp.com.ua/
# Example:
# /paysys_check.cgi?account=638&date=13.12.08%2001%3A42%3A21&hash=5237893&id=138&sum=66&testMode=0&type=1&sign=a97e377896b2630fe491d6e0d79a8f484bf357b4f5c5197e8ffc7466d1b6693d0dc892e1380ab4104bc920ccfdc808fe898524330bcefd7c7c2407668a9a845f47f693202119820cce77928a377a316c99c561c5d81811f929d3b39c0e37d893901f35e30352e3e8acd49abcbbe2033c3847d81c0bd06728d24f36e116be6d49
# OLD version
#**********************************************************
sub usmp_payments {


eval { require Crypt::OpenSSL::RSA; };
if (! $@) {
   Crypt::OpenSSL::RSA->import();
 }
else {
   print "Content-Type: text/html\n\n";
   print "Can't load 'Crypt::OpenSSL::RSA' check http://www.cpan.org";
   exit;
 }


my $CHECK_FIELD = $conf{PAYSYS_USMP_ACCOUNT_KEY} || 'UID';


my $id    = $FORM{'id'};
my $accid = $FORM{'account'};
my $summ  = $FORM{'sum'};
my $sign  = $FORM{'sign'};
my $hash  = $FORM{'hash'};
my $date  = $FORM{'date'};

my $ChequeNumber = 0;
if ($conf{PAYSYS_USMP_V2}) {
	
}

my $err_code = 0;

#Check user account
my $list = $users->list({ $CHECK_FIELD => $accid });

my $user ;
if ($users->{errno}) {
  err_trap(7, $users->{errstr});
 }
elsif ($users->{TOTAL} < 1) {
  $err_code = 2
 }
else {
  my $uid = $list->[0]->[5+$users->{SEARCH_FIELDS_COUNT}];
	$user = $users->info($uid); 
}

if (!$err_code) {
	$date =~ s/\s/%20/;
	$date =~ s/:/%3A/g;
	my $data = "account=" . $accid . "&date=" . $date . "&hash=" . $hash . "&id=" . $id . "&sum=" . $summ . "&testMode=0&type=1";
	
	if (! -f $conf{PAYSYS_USMP_KEYFILE}) {
		print "code=2";
		print "Can't find cert file.";
		return 0;
	 }
	
	my $rsa_pub = Crypt::OpenSSL::RSA->new_public_key(read_public_key($conf{PAYSYS_USMP_KEYFILE}));

	$rsa_pub->use_md5_hash();
	my $signature = pack('H*', $sign);
	if ($rsa_pub->verify($data, $signature)) {
    $payments->add($user, {SUM          => $summ,
     	                     DESCRIBE     => 'USMP', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{47}) ? 47 : '2',, 
    	                     EXT_ID       => "USMP:$id",
  	                       CHECK_EXT_ID => "USMP:$id" } );  
    if ($payments->{errno}) {
      err_trap(7, $payments->{errstr});
     }  

    $Paysys->add({ SYSTEM_ID   => 47, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$summ",
  	            UID            => "$accid", 
                IP             => '0.0.0.0',
                TRANSACTION_ID => "USMP:$id",
                INFO           => "STATUS: $err_code",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });
     }
   }

print "code=$err_code&message=Done&date=" . get_date();
}


#**********************************************************
#
#**********************************************************
sub smsproxy_payments {
#https//demo.abills.net.ua:9443/paysys_check.cgi?skey=827ccb0eea8a706c4c34a16891f84e7b&smsid=1208992493215&num=1171&operator=Tester&user_id=1234567890&cost=1.5&msg=%20Test_messages
 my $sms_num     = $FORM{num}     || 0;
 my $cost        = $FORM{cost_rur}|| 0;
 my $skey        = $FORM{skey}    || '';
 my $prefix      = $FORM{prefix}  || '';

 my %prefix_keys = ();
 my $service_key = '';
 
 if ($conf{PAYSYS_SMSPROXY_KEYS} && $conf{PAYSYS_SMSPROXY_KEYS} =~ /:/) {
   my @keys_arr = split(/,/, $conf{PAYSYS_SMSPROXY_KEYS});

   foreach my $line (@keys_arr) {
     my($num, $key)=split(/:/, $line);
     if ($num eq $sms_num) {
       $prefix_keys{$num}=$key;  
       $service_key = $key;
      }
    }
  }
 else {
   $prefix_keys{$sms_num}=$conf{PAYSYS_SMSPROXY_KEYS};  
   $service_key = $conf{PAYSYS_SMSPROXY_KEYS};
  }

 $md5->reset;
 $md5->add($service_key);
 my $digest = $md5->hexdigest();

 print "smsid: $FORM{smsid}\n";


 if ($digest ne $skey) {
   print "status:reply\n";
   print "content-type: text/plain\n\n";
   print "Wrong key!\n";
   return 0;
  }


my $code = mk_unique_value(8);
#Info section  
 my ($transaction_id, $m_secs)=split(/\./, $FORM{smsid}, 2);
 

 my $er = 1;
 $payments->exchange_info(0, { SHORT_NAME => "SMSPROXY"  });
 if ($payments->{TOTAL} > 0) {
  	$er = $payments->{ER_RATE};
   }

 if ($payments->{errno}) {
   print "status:reply\n";
   print "content-type: text/plain\n\n";
   print "PAYMENT ERROR: $payments->{errno}!\n";
   return 0;
  }
 
 $Paysys->add({ SYSTEM_ID      => 43, 
 	              DATETIME       => "'$DATE $TIME'", 
 	              SUM            => "$cost",
 	              UID            => "", 
                IP             => "0.0.0.0",
                TRANSACTION_ID => "$transaction_id",
                INFO           => "ID: $FORM{smsid}, NUM: $FORM{num}, OPERATOR: $FORM{operator}, USER_ID: $FORM{user_id}",
                PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}",
                CODE           => $code
               });


  if ($Paysys->{errno} && $Paysys->{errno} == 7) {
    print "status:reply\n";
    print "content-type: text/plain\n\n";
    print "Request dublicated $FORM{smsid}\n";
    return 0;
   }


  print "status:reply\n";
  print "content-type: text/plain\n\n";
  print $conf{PAYSYS_SMSPROXY_MSG} if ($conf{PAYSYS_SMSPROXY_MSG});
  print " CODE: $code";

}


#**********************************************************
#
#**********************************************************
sub rupay_payments {

$md5->reset;
my $checksum = '';
my $info = '';
my $user = $users->info($FORM{user_field_UID});

if ($user->{errno}) {
	$status = "ERROR: $user->{errno}";
 }
elsif ($user->{TOTAL} < 0) {
	$status = "User not exist";
 }
elsif ($FORM{rupay_site_id} ne $conf{PAYSYS_RUPAY_ID}) {
	$status = 'Not valid money account';
 }

while(my($k, $v)=each %FORM) {
  $info .= "$k, $v\n" if ($k =~ /^rupay|^user_field/);
 }


#notification
#Make checksum
if ($FORM{rupay_action} eq 'add') {
  $md5->add("$FORM{rupay_action}::$FORM{rupay_site_id}::$FORM{rupay_order_id}::$FORM{rupay_name_service}::$FORM{rupay_id}::$FORM{rupay_sum}::$FORM{rupay_user}::$FORM{rupay_email}::$FORM{rupay_data}::$conf{PAYSYS_RUPAY_SECRET_KEY}");
  $checksum = $md5->hexdigest();	

  $status = 'Preview Request';
  if ($FORM{rupay_hash} ne $checksum) {
  	$status = "Incorect checksum '$checksum'";
   }

  #Info section  
  $Paysys->add({ SYSTEM_ID      => 42, 
  	             DATETIME       => '', 
  	             SUM            => $FORM{rupay_sum},
  	             UID            => $FORM{user_field_UID}, 
                 IP             => $FORM{user_field_IP},
                 TRANSACTION_ID => "$FORM{rupay_order_id}",
                 INFO           => "STATUS, $status\n$info",
                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });
 } 
#Add paymets
elsif ($FORM{rupay_action} eq 'update') {
  #Make checksum
  $md5->add("$FORM{rupay_action}::$FORM{rupay_site_id}::$FORM{rupay_order_id}::$FORM{rupay_sum}::$FORM{rupay_id}::$FORM{rupay_data}::$FORM{rupay_status}::$conf{PAYSYS_RUPAY_SECRET_KEY}"); 
  $checksum = $md5->hexdigest();	


  if ($FORM{rupay_hash} ne $checksum) {
  	$status = 'Incorect checksum';
   }
  elsif($status eq '') {
    #Add payments
    my $er = ($FORM{'5.ER'}) ? $payments->exchange_info() : { ER_RATE => 1 } ;  
    $payments->add($user, {SUM          => $FORM{rupay_sum},
    	                     DESCRIBE     => 'RUpay', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{42}) ? 42 : '2', 
  	                       EXT_ID       => $FORM{rupay_order_id}, 
  	                       ER           => $er->{ER_RATE} } );  

    if ($payments->{errno}) {
      $info = "PAYMENT ERROR: $payments->{errno}\n";
     }
    else {
    	$status = "Added $payments->{INSERT_ID}\n";
     }
   }

  #Info section  
  $Paysys->add({ SYSTEM_ID      => 42, 
  	             DATETIME       => '', 
  	             SUM            => $FORM{rupay_sum},
  	             UID            => $FORM{user_field_UID}, 
                 IP             => $FORM{user_field_IP},
                 TRANSACTION_ID => "$FORM{rupay_order_id}",
                 INFO           => "STATUS, $status\n$info",
                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

  $output2 .= "Paysys:".$Paysys->{errno} if ($Paysys->{errno});
  $output2 .= "CHECK_SUM: $checksum\n";
 }


}

#**********************************************************
# https://merchant.webmoney.ru/conf/guide.asp
#
#**********************************************************
sub wm_payments {
#Pre request section
if($FORM{'LMI_PREREQUEST'} && $FORM{'LMI_PREREQUEST'} == 1) { 

 
 }
#Payment notification
elsif($FORM{LMI_HASH}) {
  my $checksum = wm_validate();
  my $info = '';
	my $user = $users->info($FORM{UID});
	
	my @ACCOUNTS = split(/;/, $conf{PAYSYS_WEBMONEY_ACCOUNTS});
	
  if (! in_array($FORM{LMI_PAYEE_PURSE}, \@ACCOUNTS)) {
  	$status = 'Not valid money account';
   }
  elsif (defined($FORM{LMI_MODE}) && $FORM{LMI_MODE} == 1) {
  	$status = 'Test mode';
   }
  elsif (length($FORM{LMI_HASH}) != 32 ) {
  	$status = 'Not MD5 checksum';
   }
  elsif ($FORM{LMI_HASH} ne $checksum) {
  	$status = "Incorect checksum \"$checksum/$FORM{LMI_HASH}\"";
   }
  elsif ($user->{errno}) {
		$status = "ERROR: $user->{errno}";
	 }
	elsif ($user->{TOTAL} < 0) {
		$status = "User not exist";
	 }
  else {
    #Add payments
    my $er = 1;  
    if ($FORM{LMI_PAYEE_PURSE} =~ /^(\S)/ ) {
      my $payment_unit = 'WM'.$1;
      $payments->exchange_info(0, { SHORT_NAME => "$payment_unit"  });
      if ($payments->{TOTAL} > 0) {
      	$er = $payments->{ER_RATE};
       }
     }
    
    #my $er = ($FORM{'5.ER'}) ? $payments->exchange_info() : { ER_RATE => 1 } ;  
    $payments->add($user, {SUM          => $FORM{LMI_PAYMENT_AMOUNT},
    	                     DESCRIBE     => 'Webmoney', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{41}) ? 41 : '2', 
  	                       EXT_ID       => $FORM{LMI_PAYMENT_NO}, 
  	                       ER           => $er
  	                       } );  

    if ($payments->{errno}) {
      $info = "PAYMENT ERROR: $payments->{errno}\n";
     }
    else {
    	$status = "Added $payments->{INSERT_ID}\n";
     }
   }
  
  while(my($k, $v)=each %FORM) {
    $info .= "$k, $v\n" if ($k =~ /^LMI/);
   }

  #Info section  
  $Paysys->add({ SYSTEM_ID      => 41, 
  	             DATETIME       => '', 
  	             SUM            => $FORM{LMI_PAYMENT_AMOUNT},
  	             UID            => $FORM{UID}, 
                 IP             => $FORM{IP},
                 TRANSACTION_ID => "$FORM{LMI_PAYMENT_NO}",
                 INFO           => "STATUS, $status\n$info",
                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

  $output2 .= "Paysys:".$Paysys->{errno} if ($Paysys->{errno});
  $output2 .= "CHECK_SUM: $checksum\n";
}

}


#**********************************************************
# http://portmone.com.ua/
#
#**********************************************************
#sub portmone_payments {
#
#
#  my $checksum = wm_validate();
#  my $info = '';
#	my $user = $users->info($FORM{UID});
#	
#	my @ACCOUNTS = split(/;/, $conf{PAYSYS_WEBMONEY_ACCOUNTS});
#	
#  if (! in_array($FORM{LMI_PAYEE_PURSE}, \@ACCOUNTS)) {
#  	$status = 'Not valid money account';
#  	#return 0;
#   }
#  elsif (defined($FORM{LMI_MODE}) && $FORM{LMI_MODE} == 1) {
#  	$status = 'Test mode';
#  	#return 0;
#   }
#  elsif (length($FORM{LMI_HASH}) != 32 ) {
#  	$status = 'Not MD5 checksum';
#   }
#  elsif ($FORM{LMI_HASH} ne $checksum) {
#  	$status = "Incorect checksum '$checksum'";
#   }
#  elsif ($user->{errno}) {
#		$status = "ERROR: $user->{errno}";
#	 }
#	elsif ($user->{TOTAL} < 0) {
#		$status = "User not exist";
#	 }
#  else {
#    #Add payments
#    my $er = 1;
#    
#    
#    if ($FORM{LMI_PAYEE_PURSE} =~ /^(\S)/ ) {
#      my $payment_unit = 'WM'.$1;
#      $payments->exchange_info(0, { SHORT_NAME => "$payment_unit"  });
#      if ($payments->{TOTAL} > 0) {
#      	$er = $payments->{ER_RATE};
#       }
#     }
#    
#    #my $er = ($FORM{'5.ER'}) ? $payments->exchange_info() : { ER_RATE => 1 } ;  
#    $payments->add($user, {SUM          => $FORM{LMI_PAYMENT_AMOUNT},
#    	                     DESCRIBE     => 'Webmoney', 
#    	                     METHOD       => '2', 
#  	                       EXT_ID       => $FORM{SHOPORDERNUMBER}, 
#  	                       ER           => $er
#  	                       } );  
#
#    if ($payments->{errno}) {
#      $info = "PAYMENT ERROR: $payments->{errno}\n";
#     }
#    else {
#    	$status = "Added $payments->{INSERT_ID}\n";
#     }
#   }
#  
#  while(my($k, $v)=each %FORM) {
#    $info .= "$k, $v\n" if ($k =~ /^LMI/);
#   }
#
#  #Info section  
#  $Paysys->add({ SYSTEM_ID      => 41, 
#  	             DATETIME       => '', 
#  	             SUM            => $FORM{SUM},
#  	             UID            => $FORM{UID}, 
#                 IP             => $FORM{IP},
#                 TRANSACTION_ID => "$FORM{SHOPORDERNUMBER}",
#                 INFO           => "STATUS, $status\n$info",
#                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
#               });
#
#  $output2 .= "Paysys:".$Paysys->{errno} if ($Paysys->{errno});
#  $output2 .= "CHECK_SUM: $checksum\n";
#
#
#}



#**********************************************************
# http://ukrpays.com/
# version Ver. 2.0.005
#**********************************************************
sub ukrpays_payments {
#Pre request section

if($FORM{hash}) {
  my $info = '';
  
  if ($FORM{order} =~ /(\d{8}):(\d+)/) {
  	#Info section
  	my $operation_id = $1;
  	my $domain_id    = $2;

    my $list = $user->config_list({ PARAM      => 'PAYSYS_UKRPAYS_SERVICE_ID;PAYSYS_UKRPAYS_SECRETKEY', 
  	                              DOMAIN_ID  => $domain_id,
  	                              SORT       => 2 });

    if ($user->{TOTAL}) {
      foreach my $line ( @$list ) {
    	  $conf{$line->[0]}=$line->[1];
       }
     }

    $md5->reset;
	  $md5->add($FORM{id_ups}); 
	  $md5->add($FORM{order});
	  $md5->add($FORM{note}) if (defined($FORM{note}));
    $md5->add($FORM{amount});
    $md5->add($FORM{date}); 
    $md5->add($conf{PAYSYS_UKRPAYS_SECRETKEY});

    my $checksum = $md5->hexdigest();	

	  if ($FORM{hash} ne $checksum) {
    	$status = "ERROR: Incorect checksum '$checksum'";
     }
    else {
    	$status = 'ok';
      $Paysys->add({ SYSTEM_ID      => 46, 
  	             DATETIME       => '', 
  	             SUM            => $FORM{amount},
  	             UID            => $FORM{order}, 
                 IP             => $FORM{IP} || '0.0.0.0',
                 TRANSACTION_ID => "UKRPAYS:$FORM{id_ups}",
                 INFO           => "STATUS: $status\nOPERATION_ID: $operation_id\n$info\nCards buy",
                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}",
                 DOMAIN_ID      => $domain_id,
                 STATUS         => 1,
               });

      if ($Paysys->{errno}) {
        if ($Paysys->{errno}==7) {
          $output2 = "duplicate\n";
         }
        else {
          $status = $output2;
         }
        $status = $output2;
       }
      elsif ($status !~ /ERROR/)  {
  	    $status = 'ok';
       }
     }
  	print $status;
  	return 0;
   }

  $md5->reset;
	$md5->add($FORM{id_ups}); 
	$md5->add($FORM{order});
	$md5->add($FORM{note}) if (defined($FORM{note}));
  $md5->add($FORM{amount});
  $md5->add($FORM{date}); 
  $md5->add($conf{PAYSYS_UKRPAYS_SECRETKEY});

  my $checksum = $md5->hexdigest();
	my $user = $users->info($FORM{order});

  if ($FORM{hash} ne $checksum) {
  	$status = "ERROR: Incorect checksum '$checksum'";
   }
  elsif ($user->{errno}) {
		$status = "ERROR: $user->{errno}";
	 }
	elsif ($user->{TOTAL} < 0) {
		$status = "ERROR: User not exist";
	 }
  else {
    #Add payments
    my $er = 1;    
    $payments->add($user, {SUM          => $FORM{amount},
    	                     DESCRIBE     => 'Ukrpays', 
    	                     METHOD       => ($conf{PAYSYS_PAYMENTS_METHODS} && $PAYSYS_PAYMENTS_METHODS{46}) ? 46 : '2', 
  	                       EXT_ID       => "UKRPAYS:$FORM{id_ups}", 
  	                       CHECK_EXT_ID => "UKRPAYS:$FORM{id_ups}", 
  	                       ER           => $er
  	                       } );  

    if ($payments->{errno}) {
      if ($payments->{errno} == 7) {
        $info = "dublicate\n";
       }
      else {
        $info = "ERROR: PAYMENT $payments->{errno}\n";
       }      
     }
    else {
    	$status = "Added $payments->{INSERT_ID}\n";
     }
   }
  
  while(my($k, $v)=each %FORM) {
    $info .= "$k, $v\n" if ($k !~ /__B/);
   }

  $status =~ s/'/\\'/g;
  #Info section  
  $Paysys->add({ SYSTEM_ID      => 46, 
  	             DATETIME       => '', 
  	             SUM            => $FORM{amount},
  	             UID            => $FORM{order}, 
                 IP             => $FORM{IP} || '0.0.0.0',
                 TRANSACTION_ID => "UKRPAYS:$FORM{id_ups}",
                 INFO           => "STATUS, $status\n$info",
                 PAYSYS_IP      => "$ENV{'REMOTE_ADDR'}"
               });

  if ($Paysys->{errno}) {
    if ($Paysys->{errno}==7) {
      $output2 = "dublicate\n";
     }
    else {
      $status = $output2;
     }
    $status = $output2;
   }
  elsif ($status !~ /ERROR/)  {
  	$status = 'ok';
   }
}

   print $status;
}


#**********************************************************
# Read Public Key
#**********************************************************
sub read_public_key {
  my ($filename) = @_;
  my $cert = "";

  open (CERT, "$filename") || die "Can't open '$filename' $!\n";
    while (<CERT>) {
     	$cert .= $_;
     }
  close CERT;

  return $cert;        
}

#**********************************************************
# Error Trap
#**********************************************************
sub err_trap {
  my ($err_code, $error) = @_;
  print "code=$err_code";
  die "Paysys database error: $error\n";
}

#**********************************************************
# Get Date
#**********************************************************
sub get_date {
    my ($sec, $min, $hour, $mday, $mon, $year) = (localtime time)[0, 1, 2, 3, 4, 5];
    $year -= 100;
    $mon++;
    $year = "0$year" if $year < 10;
    $mday = "0$mday" if $mday < 10;
    $mon = "0$mon" if $mon < 10;
    $hour = "0$hour" if $hour < 10;
    $min = "0$min" if $min < 10;
    $sec = "0$sec" if $sec < 10;
    
    return "$mday.$mon.$year $hour:$min:$sec";
}

#**********************************************************
# Webmoney MD5 validate
#**********************************************************
sub wm_validate {
  $md5->reset;

	$md5->add($FORM{LMI_PAYEE_PURSE}); 
	$md5->add($FORM{LMI_PAYMENT_AMOUNT});
  $md5->add($FORM{LMI_PAYMENT_NO});
  $md5->add($FORM{LMI_MODE}); 
  $md5->add($FORM{LMI_SYS_INVS_NO});
  $md5->add($FORM{LMI_SYS_TRANS_NO});
  $md5->add($FORM{LMI_SYS_TRANS_DATE});
  $md5->add($conf{PAYSYS_LMI_SECRET_KEY}); 
  #$md5->add($FORM{LMI_SECRET_KEY}); 
  $md5->add($FORM{LMI_PAYER_PURSE}); 
  $md5->add($FORM{LMI_PAYER_WM}); 

  my $digest = uc($md5->hexdigest());	
  
  return $digest;
}

#**********************************************************
# mak_log
#**********************************************************
sub mk_log {
  my ($message, $attr) = @_;
 
  if (open(FILE, ">>paysys_check.log")) {
    print FILE "\n$DATE $TIME $ENV{REMOTE_ADDR}=========================\n";
    print FILE $message;
	  close(FILE);
	 }
  else {
    print "Can't open file 'paysys_check.log' $! \n";
   }
}

1
