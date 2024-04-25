import os, re, socket, ast, datetime
from urllib.parse import quote
import numpy


import redis
if not os.environ.get('AZURE_TESTING'):
    redis_host = 'xf06bm-ioc2'
else:
    redis_host = '127.0.0.1'
class NoRedis():
    def set(self, thing, otherthing):
        return None
    def get(self, thing):
        return None
try:
    rkvs = redis.Redis(host=redis_host, port=6379, db=0)
except:
    rkvs = NoRedis()
all_references = ast.literal_eval(rkvs.get('BMM:reference:mapping').decode('UTF8'))

    
from pygments import highlight
from pygments.lexers import PythonLexer, IniLexer
from pygments.formatters import HtmlFormatter

from BMM.periodictable import edge_energy, Z_number, element_symbol, element_name

startup_dir = os.path.dirname(__file__)

class BMMDossier():
    '''A class for generating a static HTML file for documenting an XAS
    measurement at BMM.

    The concept is that the (many, many) attributes of this class will
    be accumulated as the scan plan is executed.  At the end of the
    scan sequence, the static HTML file will be generated.

    That static HTML file is made using a set of simple text templates
    which are filled in, the concatenated in a way that suitable for
    the current XAS measurement.

    It is the responsibility of the process sending the kafka messages
    to supply EVERY SINGLE ONE of the attributes.  

    attributes
    ==========
    date : str
      start date of experiment as YYYY-MM-DD
    folder : str
      target data folder, if None use folder recorded in start doc
    instrument : str
      html text for instrument DIV, supplied by instrument class
      if None, call self.instrument_default() for a placeholder
    rid : str
      reference ID number for link to Slack message log capture
    uidlist : list of str
      generated list of XAFS scan UIDs in the scan sequence

    methods
    =======
    capture_xrf
      measure an XRF spectrum and capture its metadata for use in a dossier

    cameras
      take a snapshot with each camera and capture metadata for use in a dossier

    prep_metadata
      organize metadata common to any dossier

    write_dossier
       generate the sample specific dossier file for an XAFS measurement

    raster_dossier
       generate the sample specific dossier file for a raster measurement
    
    sead_dossier
       generate the sample specific dossier file for a SEAD measurement
    
    write_manifest
       update the manifest and the 00INDEX.html file

    make_merged_triplot
       merge the scans and generate a triplot

    simple_plot
       simple, fallback plot

    instrument state
    ================

    If using one of the automated instruments (sample wheel, Linkam
    stage, LakeShore temperature controller, glancing angle stage,
    motor grid), the class implementing the instrument is responsible
    for supplying a method called dossier_entry.  Here is an example
    from the glancing angle stage class:

           def dossier_entry(self):
              thistext  =  '	    <div>\n'
              thistext +=  '	      <h3>Instrument: Glancing angle stage</h3>\n'
              thistext +=  '	      <ul>\n'
              thistext += f'               <li><b>Spinner:</b> {self.current()}</li>\n'
              thistext += f'               <li><b>Tilt angle:</b> {xafs_pitch.position - self.flat[1]:.1f}</li>\n'      
              thistext += f'               <li><b>Spinning:</b> {"yes" if self.spin else "no"}</li>\n'
              thistext +=  '	      </ul>\n'
              thistext +=  '	    </div>\n'
              return thistext

    This returns a <div> block for the HTML dossier file.  The
    contents of this text include a header3 description of the
    instrument and an unordered list of the most salient aspects of
    the current state of the instrument.

    Admittedly, requiring a method that generates suitable HTML is a
    bit unwieldy, but is allows much flexibility in how the instrument
    gets described in the dossier.

    The dossier_entry methods get used in BMM/xafs.py around line 880.

    The methods raster_dossier and sead_dossier serve this purpose for
    those measurements.

    '''

    ## these default values should still allow a dossier to be written
    ## even if parameters were not provided by the process sending the
    ## kafka message
    date = ''
    folder = None
    instrument = None
    rid = ''
    uidlist = []


    ## another dossier type...?
    npoints       = 0
    dwell         = 0
    delay         = 0
    scanuid       = None


    def __init__(self):
        self.scanlist      = ''
        #self.motors        = motor_sidebar()
        #self.manifest_file = os.path.join(user_ns['BMMuser'].folder, 'dossier', 'MANIFEST')


        
    def set_parameters(self, **kwargs):
        for k in kwargs.keys():
            if k == 'dossier':
                continue
            else:
                setattr(self, k, kwargs[k])

    def log_entry(self, logger, message):
        #if logger.name == 'BMM file manager logger' or logger.name == 'bluesky_kafka':
        print(message)
        logger.info(message)


    def write_dossier(self, bmm_catalog, logger):

        if len(self.uidlist) == 0:
            self.log_entry(logger, '*** cannot write dossier, uidlist is empty')
            return None

        ## gather information for the dossier from the start document
        ## of the first scan in the sequence
        startdoc = bmm_catalog[self.uidlist[0]].metadata['start']
        XDI = startdoc['XDI']
        if '_snapshots' in XDI:
            snapshots = XDI['_snapshots']
        else:
            snapshots = {}
        

        folder = self.folder
        if folder is None or folder == '':
            folder = XDI["_user"]["folder"]
        self.folder = folder
            
        ## test if XAS data file can be found
        if XDI['_user']['filename'] is None or XDI["_user"]["start"] is None:
            self.log_entry(logger, '*** Filename and/or start number not given.  (xafs_dossier).')
            return None
        firstfile = f'{XDI["_user"]["filename"]}.{XDI["_user"]["start"]:03d}'
        if not os.path.isfile(os.path.join(folder, firstfile)):
            self.log_entry(logger, f'*** Could not find {os.path.join(folder, firstfile)}')
            return None

        ## determine names of output dossier files
        basename     = XDI['_user']['filename']
        htmlfilename = os.path.join(folder, 'dossier/', XDI['_user']['filename']+'-01.html')
        seqnumber = 1
        if os.path.isfile(htmlfilename):
            seqnumber = 2
            while os.path.isfile(os.path.join(folder, 'dossier', "%s-%2.2d.html" % (XDI['_user']['filename'],seqnumber))):
                seqnumber += 1
            basename     = "%s-%2.2d" % (XDI['_user']['filename'],seqnumber)
            htmlfilename = os.path.join(folder, 'dossier', "%s-%2.2d.html" % (XDI['_user']['filename'],seqnumber))

        ## generate triplot as a png image (or fail gracefully)
        prjfilename, pngfilename = None, None
        try:
            if self.uidlist is not None:
                pngfilename = os.path.join(folder, 'snapshots', f"{basename}.png")
                #prjfilename = os.path.join(folder, 'prj', f"{basename}.prj")
                self.make_merged_triplot(self.uidlist, pngfilename, XDI['_user']['mode'])
        except Exception as e:
            logger.info('*** failure to make triplot\n' + str(e))


        ## sanity check the "report ID" (used to link to correct position in messagelog.html
        if self.rid is None: self.rid=''

        try:
            # dossier header
            with open(os.path.join(startup_dir, 'tmpl', 'dossier_top.tmpl')) as f:
                content = f.readlines()
            thiscontent = ''.join(content).format(measurement   = 'XAFS',
                                                  filename      = XDI['_user']['filename'],
                                                  date          = self.date,
                                                  rid           = self.rid,
                                                  seqnumber     = seqnumber, )

            # left sidebar, entry for XRF file in the case of fluorescence data
            thismode = self.plotting_mode(XDI['_user']['mode'])
            if thismode == 'xs' or thismode == 'xs1':
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_xrf_file.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(basename      = basename,
                                                       xrffile       = quote('../XRF/'+os.path.basename(XDI['_xrffile'])),
                                                       xrfuid        = snapshots['xrf_uid'], )

            # middle part of dossier
            if self.instrument is None or self.instrument == '':
                self.instrument = self.instrument_default()
            with open(os.path.join(startup_dir, 'tmpl', 'dossier_middle.tmpl')) as f:
                content = f.readlines()
            thiscontent += ''.join(content).format(basename      = basename,
                                                   scanlist      = self.generate_scanlist(bmm_catalog),  # uses self.uidlist
                                                   motors        = self.motor_sidebar(bmm_catalog),
                                                   sample        = XDI['Sample']['name'],
                                                   prep          = XDI['Sample']['prep'],
                                                   comment       = XDI['_user']['comment'],
                                                   instrument    = self.instrument,)
            

            # middle part, cameras, one at a time and only if actually snapped
            if 'webcam_uid' in snapshots and snapshots['webcam_uid'] != '':
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_img.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(snap        = quote('../snapshots/'+os.path.basename(snapshots['webcam_file'])),
                                                       uid         = snapshots['webcam_uid'],
                                                       camera      = 'webcam',
                                                       description = 'XAS web camera', )
            if 'anacam_uid' in snapshots and snapshots['anacam_uid'] != '':
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_img.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(snap        = quote('../snapshots/'+os.path.basename(snapshots['analog_file'])),
                                                       uid         = snapshots['anacam_uid'],
                                                       camera      = 'anacam',
                                                       description = 'analog pinhole camera', )
            if 'usbcam1_uid' in snapshots and snapshots['usbcam1_uid'] != '':
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_img.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(snap        = quote('../snapshots/'+os.path.basename(snapshots['usb1_file'])),
                                                       uid         = snapshots['usbcam1_uid'],
                                                       camera      = 'usbcam1',
                                                       description = 'USB camera #1', )
            if 'usbcam2_uid' in snapshots and snapshots['usbcam2_uid'] != '':
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_img.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(snap        = quote('../snapshots/'+os.path.basename(snapshots['usb2_file'])),
                                                       uid         = snapshots['usbcam2_uid'],
                                                       camera      = 'usb2cam',
                                                       description = 'USB camera #2', )
            
            # middle part, XRF and glancing angle alignment images
            if thismode == 'xs' or thismode == 'xs1':
                el = XDI['Element']['symbol']
                rois = [int(bmm_catalog[snapshots['xrf_uid']].primary.data[el+'1'][0]),
                        int(bmm_catalog[snapshots['xrf_uid']].primary.data[el+'2'][0]),
                        int(bmm_catalog[snapshots['xrf_uid']].primary.data[el+'3'][0]),
                        int(bmm_catalog[snapshots['xrf_uid']].primary.data[el+'4'][0])]
                ocrs = [int(numpy.array(bmm_catalog[snapshots['xrf_uid']].primary.data['4-element SDD_channel01_xrf']).sum()),
                        int(numpy.array(bmm_catalog[snapshots['xrf_uid']].primary.data['4-element SDD_channel02_xrf']).sum()),
                        int(numpy.array(bmm_catalog[snapshots['xrf_uid']].primary.data['4-element SDD_channel03_xrf']).sum()),
                        int(numpy.array(bmm_catalog[snapshots['xrf_uid']].primary.data['4-element SDD_channel04_xrf']).sum()) ]
                with open(os.path.join(startup_dir, 'tmpl', 'dossier_xrf_image.tmpl')) as f:
                    content = f.readlines()
                thiscontent += ''.join(content).format(xrfsnap   = quote('../XRF/'+os.path.basename(snapshots['xrf_image'])),
                                                       pccenergy = '%.1f' % XDI['_user']['pccenergy'],
                                                       ocrs      = ', '.join(map(str,ocrs)),
                                                       rois      = ', '.join(map(str,rois)),
                                                       symbol    = XDI['Element']['symbol'],)
                if 'ga_filename' in snapshots:
                    with open(os.path.join(startup_dir, 'tmpl', 'dossier_ga.tmpl')) as f:
                        content = f.readlines()
                    thiscontent += ''.join(content).format(ga_align = snapshots['ga_filename'],
                                                           ga_yuid  = snapshots['ga_yuid'],
                                                           ga_puid  = snapshots['ga_pitchuid'],
                                                           ga_fuid  = snapshots['ga_fuid'], )

            # end of dossier
            with open(os.path.join(startup_dir, 'tmpl', 'dossier_bottom.tmpl')) as f:
                content = f.readlines()
            this_ref = all_references[XDI['Element']['symbol']][3]

            # print('e0'            , '%.1f' % edge_energy(XDI['Element']['symbol'], XDI['Element']['edge']))
            # print('edge'          , XDI['Element']['edge'],)
            # print('element'       , self.element_text(XDI['Element']['symbol']),)
            # print('mode'          , XDI['_user']['mode'],)
            # print('bounds'        , ", ".join(map(str, XDI['_user']['bounds_given'])),)
            # print('steps'         , XDI['_user']['steps'],)
            # print('times'         , XDI['_user']['times'],)
            # print('reference'     , re.sub(r'(\d+)', r'<sub>\1</sub>', this_ref),)
            # print('seqstart'      , datetime.datetime.fromtimestamp(bmm_catalog[self.uidlist[0]].metadata['start']['time']).strftime('%A, %B %d, %Y %I:%M %p'),)
            # print('seqend'        , datetime.datetime.fromtimestamp(bmm_catalog[self.uidlist[-1]].metadata['stop']['time']).strftime('%A, %B %d, %Y %I:%M %p'),)
            # print('mono'          , self.mono,)
            # print('pdsmode'       , self.pdstext,)
            # print('pccenergy'     , '%.1f' % XDI['_user']['pccenergy'],)
            # print('experimenters' , XDI['_user']['experimenters'],)
            # print('gup'           , XDI['Facility']['GUP'],)
            # print('saf'           , XDI['Facility']['GUP'],)
            # print('url'           , XDI['_user']['url'],)
            # print('doi'           , XDI['_user']['doi'],)
            # print('cif'           , XDI['_user']['cif'],)
            # print('initext'       , highlight(XDI['_user']['initext'], IniLexer(),    HtmlFormatter()),)
            # print('clargs'        , highlight(XDI['_user']['clargs'],  PythonLexer(), HtmlFormatter()),)
            # print('filename'      , XDI['_user']['filename'],)

            
            thiscontent += ''.join(content).format(e0            = '%.1f' % edge_energy(XDI['Element']['symbol'], XDI['Element']['edge']),
                                                   edge          = XDI['Element']['edge'],
                                                   element       = self.element_text(XDI['Element']['symbol']),
                                                   mode          = XDI['_user']['mode'],
                                                   bounds        = ", ".join(map(str, XDI['_user']['bounds_given'])),
                                                   steps         = XDI['_user']['steps'],
                                                   times         = XDI['_user']['times'],
                                                   reference     = re.sub(r'(\d+)', r'<sub>\1</sub>', this_ref),
                                                   seqstart      = datetime.datetime.fromtimestamp(bmm_catalog[self.uidlist[0]].metadata['start']['time']).strftime('%A, %B %d, %Y %I:%M %p'),
                                                   seqend        = datetime.datetime.fromtimestamp(bmm_catalog[self.uidlist[-1]].metadata['stop']['time']).strftime('%A, %B %d, %Y %I:%M %p'),
                                                   mono          = self.mono_text(bmm_catalog),
                                                   pdsmode       = '%s  (%s)' % self.pdstext(bmm_catalog),
                                                   pccenergy     = '%.1f' % XDI['_user']['pccenergy'],
                                                   experimenters = XDI['_user']['experimenters'],
                                                   gup           = XDI['Facility']['GUP'],
                                                   saf           = XDI['Facility']['GUP'],
                                                   url           = XDI['_user']['url'],
                                                   doi           = XDI['_user']['doi'],
                                                   cif           = XDI['_user']['cif'],
                                                   initext       = highlight(XDI['_user']['initext'], IniLexer(),    HtmlFormatter()),
                                                   clargs        = highlight(XDI['_user']['clargs'],  PythonLexer(), HtmlFormatter()),
                                                   filename      = XDI['_user']['filename'],)

            with open(htmlfilename, 'a') as o:
                o.write(thiscontent)

            self.log_entry(logger, f'wrote dossier: {htmlfilename}')
        except Exception as E:
            self.log_entry(logger, f'failed to write dossier file {htmlfilename}\n' + str(E))


        self.manifest_file = os.path.join(folder, 'dossier', 'MANIFEST')            
        manifest = open(self.manifest_file, 'a')
        manifest.write(f'xafs␣{htmlfilename}\n')
        manifest.close()
        self.write_manifest('XAFS')


    def write_manifest(self, scantype='XAFS'):
        '''Update the scan manifest and the corresponding static html file.'''
        with open(self.manifest_file) as f:
            lines = [line.rstrip('\n') for line in f]

        experimentlist = ''
        for l in lines:
            (scantype, fname) = l.split('␣')
            if not os.path.isfile(fname):
                continue
            this = os.path.basename(fname)
            experimentlist += f'<li>{scantype}: <a href="./{this}">{this}</a></li>\n'

        with open(os.path.join(startup_dir, 'tmpl', 'manifest.tmpl')) as f:
            content = f.readlines()
        indexfile = os.path.join(self.folder, 'dossier', '00INDEX.html')
        o = open(indexfile, 'w')
        o.write(''.join(content).format(date           = self.date,
                                        experimentlist = experimentlist,))
        o.close()



    def plotting_mode(self, mode):
        mode = mode.lower()
        if mode == 'xs1':
            return 'xs1'
        elif any(x in mode for x in ('xs', 'fluo', 'flou', 'both')):
            return 'xs'
        #elif any(x in mode for x in ('fluo', 'flou', 'both')):
        #    return 'fluo'  # deprecated analog fluo detection
        elif mode == 'ref':
            return 'ref'
        elif mode == 'yield':
            return 'yield'
        elif mode == 'test':
            return 'test'
        elif mode == 'icit':
            return 'icit'
        elif mode == 'ici0':
            return 'ici0'
        else:
            return 'trans'

    def element_text(self, element='Po'):
        if Z_number(element) is None:
            return ''
        else:
            thistext  = f'{element} '
            thistext += f'(<a href="https://en.wikipedia.org/wiki/{element_name(element)}">'
            thistext += f'{element_name(element)}</a>, '
            thistext += f'{Z_number(element)})'
            return thistext
        
    def generate_scanlist(self, bmm_catalog):
        template = '<li><a href="../{filename}.{ext:03d}" title="Click to see the text of {filename}.{ext:03d}">{filename}.{ext:03d}</a>&nbsp;&nbsp;&nbsp;&nbsp;<a href="javascript:void(0)" onclick="toggle_visibility(\'{filename}.{ext:03d}\');" title="This is the scan number for {filename}.{ext:03d}, click to show/hide its UID">#{scanid}</a><div id="{filename}.{ext:03d}" style="display:none;"><small>{uid}</small></div></li>\n'

        text = ''
        ext = bmm_catalog[self.uidlist[0]].metadata['start']['XDI']['_user']['start']
        for u in self.uidlist:
            text += template.format(filename = bmm_catalog[u].metadata['start']['XDI']['_user']['filename'],
                                    ext      = ext,
                                    scanid   = bmm_catalog[u].metadata['start']['scan_id'],
                                    uid      = u)
            ext = ext + 1
        return text

    def mono_text(self, bmm_catalog):
        dcmx = bmm_catalog[self.uidlist[0]].baseline.data['dcm_x'][0]
        if dcmx > 10:
            return 'Si(311)'
        elif bmm_catalog[self.uidlist[0]].metadata['start']['XDI']['_user']['ththth'] is True:
            return 'Si(333)'
        else:
            return 'Si(111)'


    def pdstext(self, bmm_catalog):
        m2v = bmm_catalog[self.uidlist[0]].baseline.data['m2_vertical'][0]
        m2p = bmm_catalog[self.uidlist[0]].baseline.data['m2_pitch'][0]
        m3p = bmm_catalog[self.uidlist[0]].baseline.data['m3_pitch'][0]
        m3v = bmm_catalog[self.uidlist[0]].baseline.data['m3_vertical'][0]
        m3l = bmm_catalog[self.uidlist[0]].baseline.data['m3_lateral'][0]
        if m2v < 0: # this is a focused mode
            if m2p > 3:
                return ('XRD', 'focused at goniometer, >8 keV')
            else:
                if m3v > -2:
                    return ('A', 'focused, >8 keV')
                elif m3v > -7:
                    return ('B', 'focused, <6 keV')
                else:
                    return ('C', 'focused, 6 to 8 keV')
        else:
            if m3p < 3:
                return ('F', 'unfocused, <6 keV')
            elif m3l > 0:
                return ('D', 'unfocused, >8 keV')
            else:
                return ('E', 'unfocused, 6 to 8 keV')


            
        

    def wheel_slot(self, value):
        '''Return the current slot number for a sample wheel.'''
        slotone = -30
        angle = round(value)
        this = round((-1*slotone-15+angle) / (-15)) % 24
        if this == 0: this = 24
        return this

    def spinner(self, pos):
        '''Return the current spinner number as an integer'''
        cur = pos % 360
        here = (9-round(cur/45)) % 8
        if here == 0:
            here = 8
        return here


    
    def motor_sidebar(self, bmm_catalog):
        baseline = bmm_catalog[self.uidlist[0]].baseline.read()

        '''Generate a list of motor positions for the sidebar of the static
        html page for a scan sequence.  Return value is a long string
        with html tags and entities embedded in the string.

        All motor positions are taken from the first entry in the
        record's baseline stream.

        Parameters
        ----------
        bmm_catalog : Tiled catalog
            catalog in which to find the record for a UID string

        >>> text = dossier.motor_sidebar(bmm_catalog)

        '''
        motors = ''

        motors +=  '<span class="motorheading">XAFS stages:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>xafs_x, {baseline["xafs_x"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_y, {baseline["xafs_y"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_pitch, {baseline["xafs_pitch"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_roll, {baseline["xafs_roll"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_wheel, {baseline["xafs_wheel"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_ref, {baseline["xafs_ref"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_refx, {baseline["xafs_refx"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_refy, {baseline["xafs_refy"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_det, {baseline["xafs_det"][0]:.3f}</div>\n'
        motors += f'              <div>xafs_garot, {baseline["xafs_garot"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        motors +=  '            <span class="motorheading">Instruments:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>slot, {self.wheel_slot(float(baseline["xafs_wheel"][0]))}</div>\n'
        motors += f'              <div>spinner, {self.spinner(float(baseline["xafs_garot"][0]))}</div>\n'
        motors += f'              <div>dm3_bct, {baseline["dm3_bct"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        motors +=  '            <span class="motorheading">Slits3:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>slits3_vsize, {baseline["slits3_vsize"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_vcenter, {baseline["slits3_vcenter"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_hsize, {baseline["slits3_hsize"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_hcenter, {baseline["slits3_hcenter"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_top, {baseline["slits3_top"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_bottom, {baseline["slits3_bottom"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_inboard, {baseline["slits3_inboard"][0]:.3f}</div>\n'
        motors += f'              <div>slits3_outboard, {baseline["slits3_outboard"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        motors +=  '            <span class="motorheading">M2:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>m2_vertical, {baseline["m2_vertical"][0]:.3f}</div>\n'
        motors += f'              <div>m2_lateral, {baseline["m2_lateral"][0]:.3f}</div>\n'
        motors += f'              <div>m2_pitch, {baseline["m2_pitch"][0]:.3f}</div>\n'
        motors += f'              <div>m2_roll, {baseline["m2_roll"][0]:.3f}</div>\n'
        motors += f'              <div>m2_yaw, {baseline["m2_yaw"][0]:.3f}</div>\n'
        motors += f'              <div>m2_yu, {baseline["m2_yu"][0]:.3f}</div>\n'
        motors += f'              <div>m2_ydo, {baseline["m2_ydo"][0]:.3f}</div>\n'
        motors += f'              <div>m2_ydi, {baseline["m2_ydi"][0]:.3f}</div>\n'
        motors += f'              <div>m2_xu, {baseline["m2_xu"][0]:.3f}</div>\n'
        motors += f'              <div>m2_xd, {baseline["m2_xd"][0]:.3f}</div>\n'
        motors += f'              <div>m2_bender, {baseline["m2_bender"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        stripe = '(Rh/Pt stripe)'
        if baseline['m3_xu'][0] < 0:
            stripe = '(Si stripe)'
        motors += f'            <span class="motorheading">M3 {stripe}:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>m3_vertical, {baseline["m3_vertical"][0]:.3f}</div>\n'
        motors += f'              <div>m3_lateral, {baseline["m3_lateral"][0]:.3f}</div>\n'
        motors += f'              <div>m3_pitch, {baseline["m3_pitch"][0]:.3f}</div>\n'
        motors += f'              <div>m3_roll, {baseline["m3_roll"][0]:.3f}</div>\n'
        motors += f'              <div>m3_yaw, {baseline["m3_yaw"][0]:.3f}</div>\n'
        motors += f'              <div>m3_yu, {baseline["m3_yu"][0]:.3f}</div>\n'
        motors += f'              <div>m3_ydo, {baseline["m3_ydo"][0]:.3f}</div>\n'
        motors += f'              <div>m3_ydi, {baseline["m3_ydi"][0]:.3f}</div>\n'
        motors += f'              <div>m3_xu, {baseline["m3_xu"][0]:.3f}</div>\n'
        motors += f'              <div>m3_xd, {baseline["m3_xd"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        motors +=  '            <span class="motorheading">XAFS table:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>xt_vertical, {baseline["xafs_table_vertical"][0]:.3f}</div>\n'
        motors += f'              <div>xt_pitch, {baseline["xafs_table_pitch"][0]:.3f}</div>\n'
        motors += f'              <div>xt_roll, {baseline["xafs_table_roll"][0]:.3f}</div>\n'
        motors += f'              <div>xt_yu, {baseline["xafs_table_yu"][0]:.3f}</div>\n'
        motors += f'              <div>xt_ydo, {baseline["xafs_table_ydo"][0]:.3f}</div>\n'
        motors += f'              <div>xt_ydi, {baseline["xafs_table_ydi"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'


        motors +=  '            <span class="motorheading">Slits2:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>slits2_vsize, {baseline["slits2_vsize"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_vcenter, {baseline["slits2_vcenter"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_hsize, {baseline["slits2_hsize"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_hcenter, {baseline["slits2_hcenter"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_top, {baseline["slits2_top"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_bottom, {baseline["slits2_bottom"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_inboard, {baseline["slits2_inboard"][0]:.3f}</div>\n'
        motors += f'              <div>slits2_outboard, {baseline["slits2_outboard"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'

        motors +=  '            <span class="motorheading">Diagnostics:</span>\n'
        motors +=  '            <div id="motorgrid">\n'
        motors += f'              <div>dm3_foils, {baseline["dm3_foils"][0]:.3f}</div>\n'
        motors += f'              <div>dm2_fs, {baseline["dm2_fs"][0]:.3f}</div>\n'
        motors +=  '            </div>\n'
        
        return motors
    
    def instrument_default(self):
        thistext  =  '	    <div>\n'
        thistext +=  '	      <h3>Instrument</h3>\n'
        thistext +=  '	      <ul>\n'
        thistext +=  '               <li>(no instrument information)</li>\n'
        thistext +=  '	      </ul>\n'
        thistext +=  '	    </div>\n'
        return thistext
