"""
Simple wrapper to run coursera-downloader on Android.
Required libraries (bs4, six) are packaged along.
"""

config = {
        "username": "TODO:",
        "password": "TODO:",

        "dest_dir": "VIDEO",
        "ignorefiles": "TODO:",
        }


def download(coursename):
    args = ['-u', config["username"],
            '-p', config["password"],
            '-d', config["dest_dir"],
            coursename,
            ]
    import sys
    sys.argv += args

    from courseradownloader import main
    main()

if __name__ == '__main__':
    download("probas-001")

