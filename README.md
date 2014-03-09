coursera-dl
===========

A python package for archiving content from coursera.org (videos,
lecture notes, ...) for offline reference. Originally forked from
[https://github.com/abhirama/coursera-download][] but significantly
cleaned up and enhanced.

Some people have asked if they could donate something. If you wish you can do so here:

[![Donate](https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=A6HCYM6JBJY5N&lc=US&item_name=Dirk%20Gorissen&currency_code=GBP&bn=PP%2dDonationsBF%3abtn_donate_LG%2egif%3aNonHosted)

Installation
------------

Make sure you have installed [Python][] and [pip][].

Then simply run: `pip install coursera-dl`

Depending on your setup this will create a `coursera-dl` script in `/usr/local/bin` (linux) or
`c:\\Python2.7\\Scripts` (windows)

(to upgrade use `pip install --upgrade`)

Usage
-----

See: `coursera-dl -h`

Example usage:

<pre>
$ coursera-dl -u MYUSERNAME -p MYPASSWORD -d MYPATH algo-2012-001 ml-2012-002
</pre>

Note: you can also specify your login and password in `.netrc` file in your home directory.
Just add this line to `~/.netrc`
<pre>
machine coursera-dl login MYUSERNAME password MYPASSWORD
</pre>

Then set the permission of `~/.netrc` to `600` (owner can read and write).
<pre>
$ chmod 600 ~/.netrc
</pre>

Now you can use coursera-dl like this:

<pre>
$ coursera-dl -d MYPATH algo-2012-001 ml-2012-002
</pre>

Note: ensure you have accepted the honor code of the class before using
this script (happens the very first time you go to the class page).

  [https://github.com/abhirama/coursera-download]: https://github.com/abhirama/coursera-download
  [Python]: http://www.python.org/download/
  [pip]: http://www.pip-installer.org/en/latest/installing.html
