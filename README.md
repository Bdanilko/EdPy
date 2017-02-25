# EdPy
Microbric Edison robot using a subset of Python 2

This software is a service used by the EdPy web application to take a subset of python 2 and create a wav file 
which can be downloaded to a Microbric Edison robot. As it is a service which the web-app uses it is strictly command line!

There are a couple of main python programs:
* EdPy.py -- this will take a file of an edpy program, and compile, assembler and create a wav file for download
* EdAsm.py -- this tool can be used to assemble an assembler source file. EdPy.py does this and more! It is
  still available for working directly with the TASM assembler language
* TranStrings.py -- a tool to find all translatable strings and make sure they are used correctly. This will 
  be used when we start the translation effort
  
All of these programs must be run using python 2.7 or later, but NOT python 3.0 or later. So it is a python 2 program,
which uses some python 2.7 additions but it isn't cleanly python 3.0. All new code was developed using future statements
to use new print functionality and import functionality so should be easy to go to python 3. But some code was taken from
EdWare (token assembler bits) so it will need more work.

All of the main python programs have a 'help' option -- e.g. python2 EdPy.py --help.

Examples
--------

To get help:
<pre>
python2 EdPy.py --help
</pre>

To compile a program:
<pre>
python2 EdPy.py en_lang.json SOURCE.py
</pre>

To just check a program. This doesn't generate a wav file.
<pre>
python2 EdPy.py -c en_lang.json SOURCE.py
</pre>

Turn on debugging output and get an assembler listing
<pre>
python2 EdPy.py -d 2 -a test.lst en_lang.json SOURCE.py
</pre>

Enjoy!

Brian
