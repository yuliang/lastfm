#!/usr/bin/perl

use warnings;
use LWP::UserAgent;
use HTTP::Cookies;
use XML::Simple; #qw(:strict);
use Data::Dumper;
use CGI;

# this is going to help us by outputting errors to the browser
# so that we can debug
use CGI::Carp qw(fatalsToBrowser); 

# you'll want this to connect to a SQL database
# getting the fields submitted in the form
my $params = new CGI;

#VARIABLES TO TWEAK------------------------------------------------------
# define a  our minimum threshhold for a match between similar artists
	$minMatch = 0.60;	
	$minTagFreq = 0.70;
	#just to make it a nice percent so people understand it
	$printMinMatch = $minMatch * 100;

# define an empty variable where the user input will go
$thequery = "";
# if we find a non-empty query, tell the user what the query was
# as feedback
$queryhasrun = 0;

# this sees if something was entered in the text field when the
# button is pressed and the action has started
if ($params->param('q') ne "") {
	# assign the text in the field to the previously empty variable
	$thequery = $params->param('q');
	# a variable that allows us to tell if the query has run and
	# we've received a value.
	$queryhasrun = 1;
} else {
	#just print everything else and die. Program ends if it enters here.
	&print_top;
	&print_form;
	print "<br />";
	&print_bottom;
	exit(1);
}
# calls the subroutines to print the webpage stuff at the top
&print_top;
&print_form;

# name the user agent object created from the LWP:UserAgent module
my $user_agent = LWP::UserAgent -> new;
$user_agent->agent('UofM user agent SI601');

#set a time for timing out so it doesn't hang
$user_agent-> timeout(30);

#assign variables to be used in the URL
$api_key = "put your own api key here";

#pick an artist, any artist.
#the words entered in the field are now assigned to an artist variable
$artist = $thequery;
#defaults to an artist if nothing is entered when action starts
if ($thequery ne ""){$artitst = $thequery;}else{$artist = "Hot Chip";}
#keep a printable version of the artist name so it looks nice printed out
$printartist = $artist;

#but also create a url-friendly (adds +s) artist name to be put in the API request
$artist =~ s/\s/+/g;

#getArtistTags, takes artist, returns array of tags
$url = "http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist=$artist&api_key=$api_key";

# just being nice and creating some hashes and arrays ahead of time
undef %neighborhoodtags;
undef %artist_tags_hash;
@missingtags = ();
@uniquetags = ();
 
 # get the URL requested in $country_url
 my $response = $user_agent->get($url);
 
 # check first if there was an error fetching the XML
 if ($response->is_error) {
   # if so, print out the error
   print STDERR __LINE__, " Error: ", $response->status_line, " ", $response;
   # or else continue parsing the XML
 } else {
  
	# Create a new parser object that will take the artist's name
	  $parser = XML::Simple->new(
	  # these help put it in a more accessible format that we can access XML attributes
	  forcearray => [ 'tag' ],
		keyattr =>  {tag => 'url' },
		rootname => 'tag',
	  );
  
  # assigns a variable that we can put all the parsed XML into for access
	 my $parsed_data = $parser->XMLin($response->content);

	# *for debugging* dump the contents of the parsed page
	#print Dumper($parsed_data);

 	 # and get a pointer to the hash of tags
 	 # these are the tags for the artist
	$tagshash = $parsed_data->{'toptags'}->{'tag'};

  # now we have gotten all the tags from the XML but we want to count how many times
  # each tag appears
	for $tag (keys %{$tagshash}) {
  		$artist_tags_hash{$$tagshash{$tag}->{'name'}} = $$tagshash{$tag}->{'count'};    # store tag name and tag count to a hash
		}

} #end else
    
# stall one second so Last.fm doesn't ban us
sleep(0.1);

# setup the API URL that will be used to get the top similar artists for the originally entered artist
$simArtistsURL = "http://ws.audioscrobbler.com/2.0/?method=artist.getsimilar&artist=$artist&api_key=$api_key";

 # actually make a call to get the URL requested in $simArtistsURL
my $response = $user_agent->get($simArtistsURL);
  #here we make a pointer to the similar artists
 $simhash = $parsed_data->{'similarartists'}->{'artist'};
 # check first if there was an error fetching the XML
 if ($response->is_error) {
   # if so, print out the error
   print STDERR __LINE__, " Error: ", $response->status_line, " ", $response;
   # or else continue parsing the XML
 } else {
  
	# Create a new parser object that will take the artist's name
	  $parser = XML::Simple->new(  
	  # this makes it easier to access the similar artist attributes we want
	  forcearray => [ 'similarartist' ],
		rootname => 'similarartist',);
	
	  # assigns a variable that we can put all the parsed XML into for access
	 my $parsed_data = $parser->XMLin($response->content);
	
	
	# *for debugging* dump the contents of the parsed page
	#print Dumper($parsed_data);
	
	 # and get a pointer to the array of artists we're creating
	$similar_artists_array = $parsed_data->{'similarartists'}->{'artist'};
	
	 $size = @$similar_artists_array;   # Get size of array

	 # now we want to loop through all the similar artists to weed some out if
	 # it's the same as entered artist, or doesn't reach the defined threshold
	 # of similarity.
	foreach $item (@$similar_artists_array){
		next if ($item->{'name'} eq $artist);
		next if ($item->{'match'} < $minMatch);
		# those that survive get put in the similar artists hash
		$neighbors = $neighbors.", ".$item->{'name'};
		$simArtistsHash{$item->{'name'}} = $item->{'match'};
		
		} #end fore each
	}#end else
	
	#getUserArtists, takes a user,  returns array of artists
	for $key ( keys %simArtistsHash) {
	  # stall one second so Last.fm doesn't ban us
		sleep(0.1);
		# run the subroutine that will get the tags for the similar artist
		&getArtistsTags($key);
		#append those to a neighborhood hash of tags 
		
	} #end for
	
	#now we're going to compare the firstArtist's tags to this.  
	
	#this comparison runs two ways.  we want to find the tags which are unique to the artist
	#and we want to find tags that are in abundance in the neighborhood but not on this artist.
	#to define abundance, we will look at the number of artists in our matched neighborhood to a given tag
	#right now that's set as a tag that appears in 70% of the 
	
	#the number of artists in our neighborhood is the length of the artistshash
	my $numArtists = scalar(keys %simArtistsHash);
	
	# printing this out to the webpage...
	print "<p>There are $numArtists artists in <strong>$printartist\'s</strong> neighborhood ($printMinMatch% close). </p>";
	print "<p>These artists (or what we call neighbors) are$neighbors</p>";
	print "</div>";
		
		print "<div class='side-a'>
			<h2>Missing Tags:</h2><p>$printartist does not have these tags <em>(but most of its neighbors do)</em></p>";

		print "<ul>";
	#find missing tags that exist in 70% of the neighborhood artists, but not this artist.
	for $key (sort {$neighborhoodtags{$b}<=>$neighborhoodtags{$a};} keys %neighborhoodtags) {
		$tagfreq = $neighborhoodtags{$key} / $numArtists;
		if ($tagfreq >= $minTagFreq){

			#see if the artist has this tag
			if (!$artist_tags_hash{$key}){
				print "<li>$key</li>"; #$artist_tags_hash{$key}
				push(@missingtags, $key);	
			} #end if artist_tags
		} #end if tagfreq
	} #end for
	print "</ul></div>";
		print "<div class='side-b'><h2>Unique Tags: </h2><p> $printartist has these tags <em>(which $printartist\'s neighbors do not)</em></p>";
		#print "------------------------------------------------------------------------------\n";
		print "<ul>";
	#now the opposite.  find the tags that an artist has that don't appear in the neighborhood.
	for $key (keys %artist_tags_hash){
		if (!$neighborhoodtags{$key}){
			print "<li>$key</li>";
			push (@uniquetags, $key);
		}#end if neighborhood tags
	
	
	}#end for artist tag hash
	print "</ul></div><p >&nbsp;</p>";

  # more HTML....
	print "<div class='clearfloat'><h2>Long Tags</h2><p>Often, Tags that are many words are weird:  here are some examples for $printartist</p></div>";
	print "<div class='side-a'><h2>Long Tags for $printartist</h2><ul>";
	foreach my $unique_tag (keys %artist_tags_hash) {

		 if ($unique_tag =~ m/(\S+\s){2,}/){
			print "<li>$unique_tag</li>";
		}
	}#end for
	print "</ul></div>";
	
	print "<div class='side-b'><h2>Long Tags for the Neighborhood </h2><ul>";
	foreach my $unique_tag (keys %neighborhoodtags) {

		 if ($unique_tag =~ m/(\S+\s){2,}/){
			print "<li>$unique_tag</li>";
		}
	}#end for
	print "</ul></div>";
	
# close the </body> and </html> tags
&print_bottom;


#---------------------------------------------------------------------------------------
sub getArtistsTags($){
# move to the next item
 my $thisArtist = shift;
# prepare the API call URL that will get the tags for the given artist in the loop
my $url = "http://ws.audioscrobbler.com/2.0/?method=artist.gettoptags&artist=$thisArtist&api_key=$api_key";
 # get the URL requested in $url
my $subresponse = $user_agent->get($url);
 
 # check first if there was an error fetching the XML
 if ($subresponse->is_error) {
   # if so, print out the error
   print STDERR __LINE__, " Error: ", $subresponse->status_line, " ", $response;
   # or else continue parsing the XML
 } else {
  
# Create a new parser object that will take the artist's name
  my $parser = XML::Simple->new(
  # reformats the XML to make it easier to grab the tags and URL for the artist
   forcearray => [ 'tag' ],
    keyattr =>  {tag => 'url' },
    rootname => 'tag',
  );
# parses the XML and stores it in the variable
 my $subparsed_data = $parser->XMLin($subresponse->content);

# *for debugging* dump the contents of the parsed page
#print Dumper($parsed_data);

  # and get a pointer to the hash of tags
$tagshash = $subparsed_data->{'toptags'}->{'tag'};

# loop through each tag in this artist's hash. add this tag to the larger neighborhood
# tags hash. each time this tag is seen again the count is increased so we get
# a count of each tag
for $tag (keys %{$tagshash}) {
  	$neighborhoodtags{$$tagshash{$tag}->{'name'}}++;
} #end for

}#end else

} #end sub

#getArtistSimilarNeighborhood,takes an artist and a "match value" for how similar they need to be, returns array of artists, 



# this subroutine prints the top little bit of html to make the
# browser happy
sub print_top {
	print "Content-type: text/html\n\n";
	print "<html>";
	print "<title>LastWeirdTags - find the weird tags for an Artist on Last.fm</title>";
	print '<style type="text/css">
	@charset "UTF-8";
		body  {
			margin: 2px; 
			padding: 5px;
			color:#FFFFFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			font-size: 100%;
			background: #333;
			background-color: #333;
		}
		#wrapper {
			text-align: left;
			margin: 0px auto;
			padding: 0px;
			border:0;
			width: 900px;
			/* background: url("/path/to/your/background_cols.gif") repeat; */
		}
		.txtfield {
			font-size:24px;
			font-family:Helvetica, Arial, Tahoma, Geneva, sans-serif;
			background-color:#CFF;
			}
		.txtbtn {
			font-size:24px;
			font-family:Helvetica, Arial, Tahoma, Geneva, sans-serif;
			}
		
		.header {
			margin: 0 0 15px 0;
			background:#333;
			color:#FFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
		
		}
		.edition {
			margin: 0 0 15px 0;
			float: left;
			background:#333;
			color:#FFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			font-size: 12px;
		
		}
		li{
			list-style:none;
			padding-bottom:2px;		
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			font-style:normal;
			font-size: 100%;
			
			}
		.side-a {
			float: left;
			width: 400px;
			padding: 5px;
			margin-right: 15px;
			color:#FFFFFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
		}
		
		.side-b { 
			
			float: left;
			width: 400px;
			padding: 5px;
			color:#FFFFFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			
			
		}
		
		.footer {
			clear: both;
			color:#FFFFFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			background: #333;
		}
		
		/* Miscellaneous classes for reuse */
		.fltrt { /* this class can be used to float an element right in your page. The floated element must precede the element it should be next to on the page. */
			float: right;
			margin-left: 8px;
		}
		.fltlft { /* this class can be used to float an element left in your page. The floated element must precede the element it should be next to on the page. */
			float: left;
			margin-right: 8px;
		}
		.clearfloat {
			color:#FFFFFF;
			font-family: Helvetica, Arial, Tahoma, Geneva, sans-serif;
			background: #333;
			clear:both;
			}
	</style>';
	print '<head>';
	print "<meta name = \"viewport\" content = \"width=device-width; initial-scale=0.7; maximum-scale=1.0; user-scalable=yes; \" />  <!-- For mobile browsers -->";
	
	print '<script language="javascript"> 
function toggle(showHideDiv) {
    var ele = document.getElementById(showHideDiv);
    if(ele.style.display == "block") {
            ele.style.display = "none";
      }
    else {
        ele.style.display = "block";
    }
} 

function test() {
	alert("Hello!");
}



</script>';
	print '</head>';
	print "<body bgcolor=\"#333\">";
	
	
	
}


# print the form
sub print_form {
	print "<div class='header'>
		<h1>Welcome to the Last.fm Tag Explorer</h1>
		<p>This uses the last.fm api to check out the interesting tags for an artist.</p>
		<h2>Put an Artist here: (e.g. \"Mozart\", \"lady gaga\")</h2> \n";
	print '<form method="get" action="lastfmlab.cgi">';
	print '<input class="txtfield" name="q" type="text" value="'. $queryterm .'"><input class="txtbtn" type="Submit" value="go" onClick="javascript:toggle(\'myContent\');">'; 
	print "</form>";
	
	#print '<input name="q" size="80" type="text" value="' . $q . '"><br />';
	print '<p><em>then hit go once, then be <strong>really</strong> patient</em></p>';
	print '<div id="myContent" style="display: none;">
<img src="../../style/progress_indicator.gif" alt="progress bar" />
</div>';
	#print '<br />How similar should artists in the hood be?<br />';
	#print '<input name="m" size="3" type="text"  > <font size=\"2\">(e.g. 60% if unsure just leave it blank)</font><br /><br />';
	#print '<input type="Submit" value="Submit">';
	
	
	
}

# close the HTML tags
sub print_bottom {
	print '<br /><br />';
	print '<p></p>';
	print "<div class='edition'> <i>This script was last edited by yuliang on Jan 24, 2011</i> </div>
	";
	print '<script src="http://www.google-analytics.com/urchin.js" type="text/javascript"> 
</script> 
<script type="text/javascript"> 
_uacct = "UA-530216-3";
urchinTracker();
</script>';
	print "</body></html>\n";
}
sub print_long_tags($){
	# my $threshold = 3;
	my %hoodtags = shift;
	print "<p><strong>Long Tags in the neighborhood</strong></p><ul>";
	foreach my $unique_tag (keys %hoodtags) {
		 # if ($uniquetag =~ m/(\S+\s){(??{$threshold}),}/){
		 if ($unique_tag =~ m/(\S+\s){2,}/){
			print "<li>$unique_tag</li>";
		}
	}#end for
	print "</ul>";
}#END SUB
