import _version
import argparse
import getpass
import json
import netrc
import os
import platform
import re
import requests
import shutil
import sys
import tarfile
import time
import math
from bs4 import BeautifulSoup
from os import path
from six import print_
from util import *


class CourseraDownloader(object):

    """
    Class to download content (videos, lecture notes, ...) from coursera.org for
    use offline.

    https://github.com/dgorissen/coursera-dl

    :param username: username
    :param password: password
    :keyword proxy: http proxy, eg: foo.bar.com:1234
    :keyword parser: xml parser
    :keyword ignorefiles: comma separated list of file extensions to skip (e.g., "ppt,srt")
    :keyword clobber: allow re-downloading of existing files
    """
    BASE_URL = 'https://class.coursera.org/%s'
    HOME_URL = BASE_URL + '/class/index'
    LECTURE_URL = BASE_URL + '/lecture/index'
    QUIZ_URL = BASE_URL + '/quiz/index'
    AUTH_URL = BASE_URL + "/auth/auth_redirector?type=login&subtype=normal"
    LOGIN_URL = "https://accounts.coursera.org/api/v1/login"
    ABOUT_URL = "https://www.coursera.org/maestro/api/topic/information?topic-id=%s"

    # see
    # http://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser
    DEFAULT_PARSER = "html.parser"

    # how long to try to open a URL before timing out
    TIMEOUT = 30.0

    def __init__(self, username,
                 password,
                 proxy=None,
                 parser=DEFAULT_PARSER,
                 ignorefiles=None,
                 clobber=True,
                 max_path_part_len=None,
                 gzip_courses=False,
                 wk_filter=None):

        self.username = username
        self.password = password
        self.parser = parser

        # Split "ignorefiles" argument on commas, strip, remove prefixing dot
        # if there is one, and filter out empty tokens.
        self.ignorefiles = [x.strip()[1:] if x[0] == '.' else x.strip()
                            for x in ignorefiles.split(',') if len(x)]
        self.clobber = clobber

        self.session = None
        self.proxy = proxy
        self.max_path_part_len = max_path_part_len
        self.gzip_courses = gzip_courses

        try:
            self.wk_filter = map(
                int, wk_filter.split(",")) if wk_filter else None
        except Exception as e:
            print_("Invalid week filter, should be a comma separated list of integers", e)
            exit()

    def login(self, className):
        """
        Login into coursera and obtain the necessary session cookies.
        """
        s = requests.Session()
        if self.proxy:
            s.proxies = {'http': self.proxy}

        url = self.lecture_url_from_name(className)
        res = s.get(url, timeout=self.TIMEOUT)
        if res.status_code == 404:
            raise Exception("Unknown class %s" % className)
        res.close()

        # get the csrf token
        if 'csrf_token' not in s.cookies:
            raise Exception("Failed to find csrf cookie")

        # call the authenticator url
        LOGIN_FORM = {'email': self.username, 'password': self.password, 'webrequest':'true'}
        s.headers['Referer'] = 'https://www.coursera.org'
        s.headers['X-CSRFToken'] = s.cookies.get('csrf_token')
        s.cookies['csrftoken'] = s.cookies.get('csrf_token')

        res = s.post(self.LOGIN_URL, data=LOGIN_FORM, timeout=self.TIMEOUT)
        if res.status_code == 401:
            raise Exception("Invalid username or password")
        res.close()

        # check if we managed to login
        if 'CAUTH' not in s.cookies:
            raise Exception("Failed to authenticate as %s" % self.username)

        self.session = s

    def course_name_from_url(self, course_url):
        """Given the course URL, return the name, e.g., algo2012-p2"""
        return course_url.split('/')[3]

    def lecture_url_from_name(self, course_name):
        """Given the name of a course, return the video lecture url"""
        return self.LECTURE_URL % course_name

    # TODO: simple hack, something more elaborate needed
    def trim_path_part(self, s):
        mppl = self.max_path_part_len
        if mppl and len(s) > mppl:
            return s[:mppl]
        else:
            return s

    def get_response(self, url, retries=3, **kwargs):
        """
        Get the response
        """
        kwargs.update(timeout=self.TIMEOUT, allow_redirects=True)
        for i in range(retries):
            try:
                r = self.session.get(url, **kwargs)
                r.raise_for_status()
            except Exception as e:
                # print_("Warning: Retrying to connect url:%s" % url)
                pass
            else:
                return r
        raise e

    def get_headers(self, url):
        """
        Get the headers
        """
        r = self.get_response(url, stream=True)
        headers = r.headers
        r.close()
        return headers

    def get_page(self, url):
        """
        Get the content
        """
        r = self.get_response(url)
        page = r.content
        r.close()
        return page

    def get_json(self, url):
        """
        Get the json data
        """
        r = self.get_response(url)
        data = r.json()
        r.close()
        return data

    def get_downloadable_content(self, course_url):
        """
        Given the video lecture URL of the course, return a list of all
        downloadable resources.
        """
        print_("* Collecting downloadable content from " + course_url)

        # get the course name, and redirect to the course lecture page
        vidpage = self.get_page(course_url)

        # extract the weekly classes
        soup = BeautifulSoup(vidpage, self.parser)

        # extract the weekly classes
        weeks = soup.findAll("div", {"class": "course-item-list-header"})

        weeklyTopics = []

        # for each weekly class
        for week in weeks:
            # @note:vanos: add filter here if required
            #if not("Week 9" in str(week)): continue
            #print "ivan:debug:", week

            # title of this weeks' classes
            h3 = week.findNext('h3')

            # sometimes the first week are the hidden sample lectures, catch
            # this
            if h3.text.strip().startswith("window.onload"):
                h3txt = "Sample Lectures"
            else:
                h3txt = h3.text.strip()

            weekTopic = sanitise_filename(h3txt)
            weekTopic = self.trim_path_part(weekTopic)

            # get all the classes for the week
            ul = week.next_sibling
            lis = ul.findAll('li')
            weekClasses = []

            # for each class (= lecture)
            for li in lis:
                # the name of this class
                className = li.a.find(text=True).strip()

                # Many class names have the following format:
                #   "Something really cool (12:34)"
                # If the class name has this format, replace the colon in the
                # time with a hyphen.
                if re.match(".+\(\d?\d:\d\d\)$", className):
                    head, sep, tail = className.rpartition(":")
                    className = head + "-" + tail

                className = sanitise_filename(className)
                className = self.trim_path_part(className)

                # collect all the resources for this class (ppt, pdf, mov, ..)
                classResources = li.find(
                    'div', {'class': 'course-lecture-item-resource'})
                hrefs = classResources.findAll('a')
                resourceLinks = []

                for a in hrefs:
                    # get the hyperlink itself
                    def _clean_url(url):
                        if not url: return None
                        url = url.strip()
                        if url and not urlparse(url).scheme:
                            url = 'https://class.coursera.org' + url
                        return url
                    h = _clean_url(a.get('href'))
                    if not h:
                        continue

                    # Sometimes the raw, uncompresed source videos are available as
                    # well. Don't download them as they are huge and available in
                    # compressed form anyway.
                    if h.find('source_videos') > 0:
                        print_("   - will skip raw source video " + h)
                    else:
                        # Dont set a filename here, that will be inferred from the week
                        # titles
                        resourceLinks.append((h, None))

                # check if the video is included in the resources, if not, try
                # do download it directly
                hasvid = [x for x, _ in resourceLinks if x.find('.mp4') > 0]
                if not hasvid:
                    ll = li.find('a', {'class': 'lecture-link'})
                    lurl = clean_url(ll['data-modal-iframe'])

                    try:
                        pg = self.get_page(lurl)
                        bb = BeautifulSoup(pg, self.parser)
                        vobj = bb.find('source', type="video/mp4")

                        if not vobj:
                            print_(
                                " Warning: Failed to find video for %s" % className)
                        else:
                            vurl = clean_url(vobj['src'])
                            # build the matching filename
                            fn = className + ".mp4"
                            resourceLinks.append((vurl, fn))

                    except requests.exceptions.HTTPError as e:
                        # sometimes there is a lecture without a vidio (e.g.,
                        # genes-001) so this can happen.
                        print_(
                            " Warning: failed to open the direct video link %s: %s" % (lurl, e))

                weekClasses.append((className, resourceLinks))

            weeklyTopics.append((weekTopic, weekClasses))

        return weeklyTopics

    def download(self, url, target_dir=".", target_fname=None):
        """
        Download the url to the given filename
        """

        # get the headers
        headers = self.get_headers(url)

        # get the content length (if present)
        clen = int(headers.get('Content-Length', -1))

        # build the absolute path we are going to write to
        fname = target_fname or filename_from_header(
            headers) or filename_from_url(url)

        # split off the extension
        basename, ext = path.splitext(fname)

        # ensure it respects mppl
        fname = self.trim_path_part(basename) + ext

        # check if we should skip it (remember to remove the leading .)
        if ext and ext[1:] in self.ignorefiles:
            print_('    - skipping "%s" (extension ignored)' % fname)
            return

        filepath = path.join(target_dir, fname)

        dl = True
        if path.exists(filepath):
            if not self.clobber: print_('    - skipping "%s" (already exists, --no-clobber)' % fname)
            if self.clobber and clen > 0:
                fs = path.getsize(filepath)
                delta = math.fabs(clen - fs)

                # there are cases when a file was not completely downloaded or
                # something went wront that meant the file on disk is
                # unreadable. The file on disk my be smaller or larger (!) than
                # the reported content length in those cases.
                # Hence we overwrite the file if the reported content length is
                # different than what we have already by at least k bytes (arbitrary)

                # TODO this is still not foolproof as the fundamental problem is that the content length cannot be trusted
                # so this really needs to be avoided and replaced by something
                # else, eg., explicitly storing what downloaded correctly
                if delta > 10:
                    print_(
                        '    - "%s" seems corrupt, downloading again' % fname)
                else:
                    print_('    - "%s" already exists, skipping' % fname)
                    dl = False
            else:
                # missing or invalid content length
                # assume all is ok...
                dl = False
        else:
            # Detect renamed files
            existing, short = find_renamed(filepath, clen)
            if existing:
                print_('    - "%s" seems to be a copy of "%s", renaming existing file' %
                       (fname, short))
                os.rename(existing, filepath)
                dl = False

        try:
            if dl:
                print_('    - Downloading', fname)
                response = self.get_response(url, stream=True)
                full_size = clen
                done_size = 0
                slice_size = 524288  # 512KB buffer
                last_time = time.time()
                with open(filepath, 'wb') as f:
                    for data in response.iter_content(chunk_size=slice_size):
                        f.write(data)
                        try:
                            percent = int(float(done_size) / full_size * 100)
                        except:
                            percent = 0
                        try:
                            cur_time = time.time()
                            speed = float(slice_size) / float(
                                cur_time - last_time)
                            last_time = cur_time
                        except:
                            speed = 0
                        if speed < 1024:
                            speed_str = '{:.1f} B/s'.format(speed)
                        elif speed < 1048576:
                            speed_str = '{:.1f} KB/s'.format(speed / 1024)
                        else:
                            speed_str = '{:.1f} MB/s'.format(speed / 1048576)
                        status_str = 'status: {:2d}% {}'.format(
                            percent, speed_str)
                        sys.stdout.write(
                            status_str + ' ' * (25 - len(status_str)) + '\r')
                        sys.stdout.flush()
                        done_size += slice_size
                response.close()
                sys.stdout.write(' ' * 25 + '\r')
                sys.stdout.flush()
        except Exception as e:
            print_("Failed to download url %s to %s: %s" % (url, filepath, e))

    def download_about(self, cname, course_dir):
        """
        Download the 'about' json file
        """
        fn = os.path.join(course_dir, cname + '-about.json')

        # get the base course name (without the -00x suffix)
        base_name = re.split('(-[0-9]+)', cname)[0]

        # get the json
        about_url = self.ABOUT_URL % base_name
        data = self.get_json(about_url)

        # pretty print to file
        with open(fn, 'w') as f:
            json_data = json.dumps(data, indent=4, separators=(',', ':'))
            f.write(json_data)

    def download_course(self, cname, dest_dir=".", reverse_sections=False, gzip_courses=False):
        """
        Download all the contents (quizzes, videos, lecture notes, ...)
        of the course to the given destination directory (defaults to .)
        """
        # get the lecture url
        course_url = self.lecture_url_from_name(cname)

        weeklyTopics = self.get_downloadable_content(course_url)
        if not weeklyTopics:
            print_(" Warning: no downloadable content found for %s, did you accept the honour code?" %
                   cname)
            return
        else:
            print_('* Got all downloadable content for ' + cname)

        if reverse_sections:
            weeklyTopics.reverse()
            print_("* Weekly modules reversed")

        # where the course will be downloaded to
        course_dir = path.abspath(path.join(dest_dir, cname))

        # ensure the course dir exists
        if not path.exists(course_dir):
            os.makedirs(course_dir)

        print_("* " + cname + " will be downloaded to " + course_dir)

        # download the standard pages
        print_(" - Downloading lecture/syllabus pages")
        self.download(self.HOME_URL %
                      cname, target_dir=course_dir, target_fname="index.html")
        self.download(course_url,
                      target_dir=course_dir, target_fname="lectures.html")
        try:
            self.download_about(cname, course_dir)
        except Exception as e:
            print_("Warning: failed to download about file", e)

        # now download the actual content (video's, lecture notes, ...)
        for j, (weeklyTopic, weekClasses) in enumerate(weeklyTopics, start=1):

            if self.wk_filter and j not in self.wk_filter:
                print_(" - skipping %s (idx = %s), as it is not in the week filter" %
                       (weeklyTopic, j))
                continue

            # add a numeric prefix to the week directory name to ensure
            # chronological ordering
            wkdirname = str(j).zfill(2) + " - " + weeklyTopic

            # ensure the week dir exists
            wkdir = path.join(course_dir, wkdirname)
            if not path.exists(wkdir):
                os.makedirs(wkdir)

            print_(" - " + weeklyTopic)

            for i, (className, classResources) in enumerate(weekClasses, start=1):
                # @hack:vanos: do not create a separate directory for each class
                if True:
                    clsdir = wkdir
                else:
                    # ensure chronological ordering
                    clsdirname = str(i).zfill(2) + " - " + className
                    clsdir = path.join(wkdir,clsdirname)

                    if not path.exists(clsdir):
                        os.makedirs(clsdir)
                print_("  - Downloading resources for " + className)

                # download each resource
                for classResource, tfname in classResources:
                    try:
                        self.download(
                            classResource, target_dir=clsdir, target_fname=tfname)
                    except Exception as e:
                        print_("    - failed: ", classResource, e)

        if gzip_courses:
            tar_file_name = cname + ".tar.gz"
            print_("Compressing and storing as " + tar_file_name)
            tar = tarfile.open(os.path.join(dest_dir, tar_file_name), 'w:gz')
            tar.add(os.path.join(dest_dir, cname), arcname=cname)
            tar.close()
            print_("Compression complete. Cleaning up.")
            shutil.rmtree(os.path.join(dest_dir, cname))


def get_netrc_creds():
    """
    Read username/password from the users' netrc file. Returns None if no
    coursera credentials can be found.
    """
    # inspired by https://github.com/jplehmann/coursera

    if platform.system() == 'Windows':
        # where could the netrc file be hiding, try a number of places
        env_vars = ["HOME", "HOMEDRIVE",
                    "HOMEPATH", "USERPROFILE", "SYSTEMDRIVE"]
        env_dirs = [os.environ[e] for e in env_vars if os.environ.get(e, None)]

        # also try the root/cur dirs
        env_dirs += ["C:", ""]

        # possible filenames
        file_names = [".netrc", "_netrc"]

        # all possible paths
        paths = [path.join(dir, fn) for dir in env_dirs for fn in file_names]
    else:
        # on *nix just put None, and the correct default will be used
        paths = [None]

    # try the paths one by one and return the first one that works
    creds = None
    for p in paths:
        try:
            auths = netrc.netrc(p).authenticators('coursera-dl')
            creds = (auths[0], auths[2])
            print_("Credentials found in .netrc file")
            break
        except (IOError, TypeError, netrc.NetrcParseError) as e:
            pass

    return creds


def normalize_string(str):
    return ''.join(x for x in str if x not in ' \t-_()"01234567890').lower()


def find_renamed(filename, size):
    fpath, name = path.split(filename)
    name, ext = path.splitext(name)
    name = normalize_string(name)

    if not path.exists(fpath):
        return None, None

    files = os.listdir(fpath)
    if files:
        for f in files:
            fname, fext = path.splitext(f)
            fname = normalize_string(fname)
            if fname == name and fext == ext:
                fullname = os.path.join(fpath, f)
                if path.getsize(fullname) == size:
                    return fullname, f

    return None, None


def main():
    # parse the commandline arguments
    parser = argparse.ArgumentParser(
        description='Download Coursera.org course videos/docs for offline use.')
    parser.add_argument("-u", dest='username', type=str,
                        help='coursera username (.netrc used if omitted)')
    parser.add_argument(
        "-p", dest='password', type=str, help='coursera password')
    parser.add_argument("-d", dest='dest_dir', type=str, default=".",
                        help='destination directory where everything will be saved')
    parser.add_argument("-n", dest='ignorefiles', type=str, default="",
                        help='comma-separated list of file extensions to skip, e.g., "ppt,srt,pdf"')
    parser.add_argument(
        "-q", dest='parser', type=str, default=CourseraDownloader.DEFAULT_PARSER,
        help="the html parser to use, see http://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser")
    parser.add_argument("-x", dest='proxy', type=str,
                        default=None, help="proxy to use, e.g., foo.bar.com:3125")
    parser.add_argument("--no-clobber", dest='clobber', default=True, action="store_false", help="Don't re-download existing files")
    parser.add_argument(
        "--reverse-sections", dest='reverse', action="store_true",
        default=False, help="download and save the sections in reverse order")
    parser.add_argument('course_names', nargs="+", metavar='<course name>',
                        type=str, help='one or more course names from the url (e.g., comnets-2012-001)')
    parser.add_argument("--gz",
                        dest='gzip_courses', action="store_true", default=False, help='Tarball courses for archival storage (folders get deleted)')
    parser.add_argument("-mppl", dest='mppl', type=int, default=100,
                        help='Maximum length of filenames/dirs in a path (windows only)')
    parser.add_argument("-w", dest='wkfilter', type=str, default=None,
                        help="Comma separted list of sequence/lesson/week numbers to download e.g., 1,3,8")
    args = parser.parse_args()

    # check the parser
    html_parser = args.parser
    if html_parser == "html.parser" and sys.version_info < (2, 7, 3):
        print_(
            " Warning: built-in 'html.parser' may cause problems on Python < 2.7.3")

    print_("Coursera-dl v%s (%s)" % (_version.__version__, html_parser))

    # search for login credentials in .netrc file if username hasn't been
    # provided in command-line args
    username, password = args.username, args.password
    if not username:
        creds = get_netrc_creds()
        if not creds:
            raise Exception(
                "No username passed and no .netrc credentials found (check a netrc file exists and has the correct permissions), unable to login")
        else:
            username, password = creds
    else:
        # prompt the user for his password if not specified
        if not password:
            password = getpass.getpass()

    # should we be trimming paths?
    # TODO: this is a simple hack, something more elaborate needed
    mppl = None
    if args.mppl and args.mppl > 0:
        #if mppl specified, always use that
        mppl = args.mppl
    elif platform.system() == "Windows":
        # if mppl is not specified on windows set manually
        mppl = 90
        print_("Maximum length of a path component set to %s" % mppl)
    else:
        # linux max path length is typically around 4060 so assume thats ok
        pass

    # instantiate the downloader class
    d = CourseraDownloader(
        username,
        password,
        proxy=args.proxy,
        parser=html_parser,
        ignorefiles=args.ignorefiles,
        clobber=args.clobber,
        max_path_part_len=mppl,
        gzip_courses=args.gzip_courses,
        wk_filter=args.wkfilter
    )

    # authenticate, only need to do this once but need a classaname to get hold
    # of the csrf token, so simply pass the first one
    print_("Logging in as '%s'..." % username)
    d.login(args.course_names[0])

    # download the content
    for i, cn in enumerate(args.course_names, start=1):
        print_("\nCourse %s of %s" % (i, len(args.course_names)))
        d.download_course(cn, dest_dir=args.dest_dir,
                          reverse_sections=args.reverse, gzip_courses=args.gzip_courses)

if __name__ == '__main__':
    main()

