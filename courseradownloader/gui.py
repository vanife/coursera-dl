import platform
import getpass
from six import print_
import sys
import _version

try:
    import Tkinter as Tk
    import ttk
    import tkFileDialog
    import tkMessageBox

except ImportError:
    print 'Error: Tkinter module not found: Please use command line version instead'

import courseradownloader as CS

queue = []
courses = []
data_collected = False

class Interface(ttk.Frame):
    def __init__(self,parent=None):
        ttk.Frame.__init__(self,parent)
        self.parent = parent
        self.reverse = Tk.IntVar()
        self.gzip_courses = Tk.IntVar()
        self.remember_Me = Tk.IntVar()
        self.gzip_courses.set(0)
        self.reverse.set(0)
        self.InitUI()

    def InitUI(self):
        """Creates the base Interface"""
        # The UI wiedgets
        self.username_label = ttk.Label(self.parent, text='E-mail : ',anchor= Tk.W)
        self.username = ttk.Entry(self.parent, width=40)

        self.password_label = ttk.Label(self.parent, text='Password : ',anchor= Tk.W)
        self.password = ttk.Entry(self.parent,show='*', width=40)

        self.remember_Me_checkbox = ttk.Checkbutton(self.parent,text='Remember Me',variable=self.remember_Me,onvalue=1,offvalue=0)

        self.courseName_label = ttk.Label(self.parent,text='Course Name : ',anchor= Tk.W)
        self.courseName = ttk.Entry(self.parent, width=40)

        self.wkfilter_label = ttk.Label(self.parent,text='Weeks : ',anchor=Tk.W)
        self.wkfilter = ttk.Entry(self.parent,width=40)

        self.proxy_label = ttk.Label(self.parent, text='Proxy** : ',anchor= Tk.NW)
        self.proxy = ttk.Entry(self.parent, width=40)

        self.parser_label = ttk.Label(self.parent,text='Parser** : ')
        self.parser = ttk.Entry(self.parent,width=40)

        self.ignoreFiles_label = ttk.Label(self.parent,text='Ignored Files**  : ',anchor= Tk.W)
        self.ignoreFiles = ttk.Entry(self.parent, width=40)

        self.mppl_label = ttk.Label(self.parent,text='MPPL** : ',anchor= Tk.W)
        self.mppl_entry = ttk.Entry(self.parent,width=40)

        self.gzip_courses_label = ttk.Label(self.parent,text='gzip courses : ',anchor= Tk.W)
        self.gzip_courses_True = ttk.Radiobutton(self.parent,text='True',value=1,width=5, variable=self.gzip_courses)
        self.gzip_courses_False = ttk.Radiobutton(self.parent,text='False',value=0,width=5, variable=self.gzip_courses)

        self.reverse_label = ttk.Label(self.parent,text='Reverse Sections : ',anchor= Tk.W)
        self.reverse_true = ttk.Radiobutton(self.parent, text='True',value=1, width=5, variable=self.reverse)
        self.reverse_false = ttk.Radiobutton(self.parent,text='False',value=0,width=5, variable=self.reverse)

        self.download_button = ttk.Button(self.parent,text='Download',command=self.submit_data)

        self.dest_button = ttk.Button(self.parent,text='Select Folder',command=self.select_dest)

        # Grid Allocation
        self.username_label.grid(column=0,row=0)
        self.username.grid(column=1,row=0,columnspan=2)
        self.password_label.grid(column=0,row=1)
        self.password.grid(column=1,row=1,columnspan=2)
        self.remember_Me_checkbox.grid(column=1,row=3)
        self.courseName_label.grid(column=0,row=4)
        self.courseName.grid(column=1,row=4,columnspan=2)

        self.wkfilter_label.grid(column=0,row=5)
        self.wkfilter.grid(column=1,row=5,columnspan=2)
        self.proxy_label.grid(column=0,row=7)
        self.proxy.grid(column=1,row=7,columnspan=2)
        self.parser_label.grid(column=0,row=8)
        self.parser.grid(column=1,row=8,columnspan=2)
        self.ignoreFiles_label.grid(column=0,row=9)
        self.ignoreFiles.grid(column=1,row=9,columnspan=2)
        self.mppl_label.grid(column=0,row=10)
        self.mppl_entry.grid(column=1,row=10,columnspan=2)


        self.gzip_courses_label.grid(column=0,row=11)
        self.gzip_courses_True.grid(column=1,row=11)
        self.gzip_courses_False.grid(column=2,row=11)


        self.reverse_label.grid(column=0,row=12)
        self.reverse_true.grid(column=1,row=12)
        self.reverse_false.grid(column=2,row=12)
        self.dest_button.grid(column=2,row=16,columnspan=2)
        self.download_button.grid(column=0,row=16)

    def select_dest(self):
        """The tk file dialog box"""
        self.destination = tkFileDialog.askdirectory()
        return self.destination

    def submit_data(self):
        global data_collected
        """When the download button is pressed, this function is executed"""
        self.checkbox_validator()
        self.sort_to_send()
        data_collected = True
        self.destruct()


    def destruct(self):
        """Prompts the user for confirmation and if so execute download and close the gui"""
        if tkMessageBox.askokcancel(message='Download would start upon closing the Interface, If any changes are to be made to the credentials Please do so by selecting Cancel'):
            self.parent.destroy()

    def sort_to_send(self):
        """The data is collected and prepared here"""
        course_names = self.courseName.get().split()
        courses.append(*course_names)
        self.Init_data = {}

        if not self.username.get():
            creds = CS.get_netrc_creds()
            if not creds:
                raise Exception("No username passed and no .netrc credentials found, unable to login")
            else:
                username, password = creds
        else:
            username = self.username.get()
            # prompt the user for his password if not specified
            if not self.password.get():
                password = getpass.getpass()
            else:
                password = self.password.get()


        # should we be trimming paths?
        #TODO: this is a simple hack, something more elaborate needed
        mppl = None
        if self.mppl_entry.get():
            if platform.system() == "Windows":
                mppl = 90
                print "Maximum length of a path component set to %s" % mppl
            else:
                # linux max path length is typically around 4060 so assume thats ok
                pass

        self.Init_data['max_path_part_len'] = mppl

        if self.proxy.get():
             self.Init_data['proxy']= self.proxy.get()

        if self.parser.get():
            self.Init_data['parser'] = self.parser.get()

        if self.gzip_courses:
            self.Init_data['gzip_courses'] = True

        if self.wkfilter.get():
            self.Init_data['wk_filter'] = self.wkfilter.get()

        if self.ignoreFiles.get():
            self.Init_data['ignorefiles']= self.ignoreFiles.get()
        else:
        # Ignorefiles is a bit buggy, as it would cause a AttributeError if not passed an empty string if the user hasn't entered anything
            self.Init_data['ignorefiles']= ''


        queue.append([username,password])
        queue.append(self.Init_data)
        queue.append([self.destination,
                    bool(self.reverse.get()),
                    bool(self.gzip_courses.get())])


    def checkbox_validator(self):
        """If the remember me checkbox is ticked, it will create a _.netrc file relative to gui.py"""
        # Needs to be fixed as this feature doesn't function as expected
        if self.remember_Me.get() is 1 and self.username.get() is not '' and self.password.get() is not '':
            with open("_.netrc","w") as creds:
                creds.write('machine coursera-dl login ' +  str(self.username.get()) + ' password ' + str(self.password.get()))


def download():
    """This function uses the data stored in the queues to inititiate the download"""
    # check the parser
    if 'parser' in queue[1]:
        html_parser = queue[1]['parser']
    else:
        html_parser = CS.CourseraDownloader.DEFAULT_PARSER

        if html_parser == "html.parser" and sys.version_info < (2, 7, 3):
            print_(
                " Warning: built-in 'html.parser' may cause problems on Python < 2.7.3")
        print_("Coursera-dl v%s (%s)" % (_version.__version__, html_parser))

    d = CS.CourseraDownloader(*queue[0],**queue[1])

    print_("Logging in as '%s'..." % queue[0][0])
    d.login(courses[0])

    for i, cn in enumerate(courses, start=1):
        print_("\nCourse %s of %s" % (i, len(courses)))
        d.download_course(cn, dest_dir=queue[2][0],
                          reverse_sections=queue[2][1],
                          gzip_courses=queue[2][2])


root = Tk.Tk()
root.title('Coursera-dl')
root.geometry("350x280")
app =  Interface(root)
app.mainloop()

# In case a user just closes the Tkinter window, It is vital that the download function isn't called and the program itself quits
if data_collected:
    download()
