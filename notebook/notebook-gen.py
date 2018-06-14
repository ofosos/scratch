import jinja2 as j

# Generate postscript to print a dotted grid notebook including page
# numbers and 2 pages in front and back which are empyt (technical
# reasons).

# Run and pipe to notebook.ps
# Then do
#   ps2pdf -sPAPERSIZE=a5 notebook.ps
#   pdfbook --batch --signature 4 notebook.pdf 1-16 notebook.pdf 17-32 notebook.pdf 33-48 notebook.pdf 49-64
# Print all four files with duplex enabled.

dotted_page_tx = """
%%Page: {{pagenum}} {{pagenum}}

/displaypgnumber
{
    .5 setgray
    {{vispage}} 2 mod dup
    0 eq 
    {
        5 15 moveto
    } if
    1 eq
    {
        395 15 moveto
    } if

    /Times-Roman findfont
    12 scalefont

    setfont
    show
} def

({{vispage}}) displaypgnumber

/dotgrid
{
    0 1 38 { % i 
	0 1 26 { % j
	    newpath
	    dup 14 mul 20 add % x * j
	    2 index 14 mul 30 add % y * i
	    1 0 360 arc closepath
	    .8 setgray fill
	    pop
	} for
	pop
    } for
} def

dotgrid

showpage
"""

dotted_page = j.Template(dotted_page_tx)

empty_page_tx = """
%%Page: {{pagenum}} {{pagenum}}

showpage
"""

empty_page = j.Template(empty_page_tx)

preamble_tx = """
%!PS-Adobe-3.0
%%Creator: Mark Meyer (handwritten)
%%Title: Standard Calendar
%%CreationDate: 2018-06-12
%%DocumentData: Clean7Bit
%%Origin: 0 0
%%BoundingBox: 0 0 420 595
%%Orientation: Portrait
%%DocumentMedia: Plain 420 595 80 white ( )
%%LanguageLevel: 3
%%Pages: 4
%%EndComments
"""

preamble = j.Template(preamble_tx)

postscript_tx = """
%%EOF
"""

postscript = j.Template(postscript_tx)

# here comes the document

pagenum = 1
vispage = 1

print(preamble.render())

for i in range(2):
    print(empty_page.render(pagenum=pagenum))
    pagenum = pagenum + 1

for i in range(60):
    print(dotted_page.render(pagenum=pagenum, vispage=vispage))
    pagenum = pagenum + 1
    vispage = vispage + 1

for i in range(2):
    print(empty_page.render(pagenum=pagenum))
    pagenum = pagenum + 1

print(postscript.render())

