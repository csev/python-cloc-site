PYTHON CLOC MINI-SITE

Course: Python for Everybody with AI (CLOC-502)
Campus course: SI 502

Files:
  app.py           Site server, UTM tracking, and live results
  index.html       Home page (UTM visits are recorded when served by app.py)
  about.html       Short explanation of the CLOC model
  utm.sqlite       SQLite data file (created automatically on first home-page hit)
  styles.css       Layout and styling
  script.js        Click-to-open image modal
  assets/          Home page and about page images

Run locally with the Python standard library. No packages or build step:

  python3 app.py

Then open http://127.0.0.1:8080/

HOST and PORT change the bind address (defaults: 127.0.0.1 and 8080).
app.py also exposes a WSGI callable named application, and it runs as a
CGI script when GATEWAY_INTERFACE is set.

Point python.dr-chuck.com at this folder and let the WSGI app serve it.

UTM TRACKING
  Home page visits that include standard utm_* query parameters are recorded.
  Example:
    http://127.0.0.1:8080/?utm_source=email&utm_medium=newsletter&utm_campaign=fall

  A bare utm parameter is stored as utm_source:
    http://127.0.0.1:8080/?utm=qr

  View live counts:
    http://127.0.0.1:8080/utm-live

  Storage columns: utm_string, count, first_use, last_use (UTC).
  Cap: 250 distinct UTM strings. Extra rows are deleted by oldest last_use.
  Visits with no UTM are stored as (none) and are never pruned.

  Optional password for viewing results (tracking itself is never passworded):
    Create utm-password.txt in this folder containing only the password.
    While that file exists and is non-empty, /utm-live asks for it.
    Delete the file to leave viewing open. Do not commit utm-password.txt.

IMPORTANT LINK CHECK
On the home page:
  On-campus registration (U-M credit):
    https://wolverineaccess.umich.edu/

On both pages:
  Register:
    https://si-ali.catalog.instructure.com/courses/python-for-everybody-with-ai
  Course dashboard:
    https://si-ali.catalog.instructure.com/dashboard/in-progress

  The register URL follows the catalog slug pattern. As of 2026-10-11 the
  catalog has not published that course yet (only the Django and Computer
  Architecture listings exist). Update both register links when it does.

On both pages:
  LinkedIn article:
    https://www.linkedin.com/pulse/campus-linked-open-course-charles-severance-hjccc/
  YouTube video:
    https://www.youtube.com/watch?v=vaEBaRATTt8&list=PLQqtpRlfsBek&index=2
  First week welcome video:
    https://www.youtube.com/watch?v=0lUAYNDl-mM&list=PLQqtpRlfsBek&index=1

On about.html only:
  Financial aid:
    https://forms.gle/gyRefPW8MBiSUPxJ7
  Master Programmer Curriculum:
    https://www.masterprogrammer.com

External links open in a new tab.

The Django site's Google tag (G-CMHFYWME8L) is not copied here.
Add a separate measurement id on these pages if this course needs analytics.
