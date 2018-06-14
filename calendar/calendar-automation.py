from lxml import etree as et
import calendar as cal
import datetime as dt
import subprocess as sp
import itertools as ito

def transform_element(id, el, replace):
    els = [x for x in el if x.tag == '{http://www.w3.org/2000/svg}tspan']
    for tspan in els:
        tspan.text = replace[id]

def interpolate(replace):
    print('Processing week {}'.format(replace['week']))

    res = []

    with open('calendar-leftsvg.svg', 'rb') as lf:
        left_xml = et.fromstring(lf.read())
        
        for id in replace.keys():
            els = left_xml.xpath("//*[@id = '{}']".format(id))
            if els:
                for el in els:
                    transform_element(id, el, replace)

        with open('{}-{}-left-out.svg'.format(replace['year'],
                                               replace['week']),
                  'wb') as lo:
            lo.write(et.tostring(left_xml))
            res.append('{}-{}-left-out.svg'.format(replace['year'],
                                                   replace['week']))


    with open('calendar-rightsvg.svg', 'rb') as rf:
        right_xml = et.fromstring(rf.read())
        for id in replace.keys():
            els = right_xml.xpath("//*[@id = '{}']".format(id))
            if els:
                for el in els:
                    transform_element(id, el, replace)

        with open('{}-{}-right-out.svg'.format(replace['year'],
                                               replace['week']),
                  'wb') as ro:
            ro.write(et.tostring(right_xml))
            res.append('{}-{}-right-out.svg'.format(replace['year'],
                                                   replace['week']))

    return res


year = 2018
startmonth = 7
lengthmonths = 6

# keep track of the generated SVG files
gensvg = []

# keep track of the last day we already processed
last_day = dt.date(1970, 1, 1)

for i in range(lengthmonths):
    c = cal.Calendar(cal.MONDAY)
    weeks = c.monthdatescalendar(year, startmonth + i)

    for week in weeks:
        if week[0] <= last_day:
            continue

        ip_dict = {}

        ip_dict['year'] = str(year)
        ip_dict['month'] = str(startmonth + i)
        ip_dict['week'] = str(week[0].isocalendar()[1])
        ip_dict['monday'] = str(week[0].day)
        ip_dict['tuesday'] = str(week[1].day)
        ip_dict['wednesday'] = str(week[2].day)
        ip_dict['thursday'] = str(week[3].day)
        ip_dict['friday'] = str(week[4].day)
        ip_dict['saturday'] = str(week[5].day)
        ip_dict['sunday'] = str(week[6].day)

        last_day = week[6]

        gensvg.extend(interpolate(ip_dict))

def inkscape_print(filename):
    out = '{}.pdf'.format(filename)
    re = sp.call(["inkscape", "-f", filename, "-A", out])
    if re != 0:
        raise Exception("Inscape failed to convert file {}".format(filename))
    return out

def create_booklet(filelist, num):
    out = 'booklet-{}.pdf'.format(num)
    union = 'union-{}.pdf'.format(num)

    callout = ['pdfunite']
    callout.extend(list(filelist))
    callout.append(union)

    re = sp.call(callout)
    if re != 0:
        raise Exception("Failed to create union PDF {}".format(filelist))

    re = sp.call(["pdfbook", "--outfile", out, "--signature", "4", union])
    if re != 0:
        raise Exception("Failed to create booklet PDF {}".format(union))

    return out

genpdf = [inkscape_print(x) for x in gensvg]

genbook = []

genpdf.insert(0, 'empty-a5.pdf')
genpdf.insert(0, 'empty-a5.pdf')
genpdf.insert(0, 'empty-a5.pdf')

genpdf.append('empty-a5.pdf')
genpdf.append('empty-a5.pdf')

for num, sig in ito.groupby(enumerate(genpdf),
                            lambda x: divmod(x[0], 16)[0]):
    re = create_booklet([x[1] for x in sig], num)
    print("Create booklet {}".format(re))
    genbook.append(re)
