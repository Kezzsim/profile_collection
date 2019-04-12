
from ophyd import QuadEM, Component as Cpt, EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV, Signal
import datetime
import copy

run_report(__file__)

bmm_metadata_stub = {'XDI,Beamline,name':        'BMM (06BM) -- Beamline for Materials Measurement',
                     'XDI,Beamline,collimation': 'paraboloid mirror, 5 nm Rh on 30 nm Pt',
                     'XDI,Facility,name':        'NSLS-II',
                     'XDI,Facility,energy':      '3 GeV',
                     'XDI,Beamline,xray_source': 'NSLS-II three-pole wiggler',
                     'XDI,Column,01':            'energy eV',
                     'XDI,Column,02':            'requested energy eV',
                     'XDI,Column,03':            'measurement time sec',
                     'XDI,Column,04':            'mu(E)',
                     'XDI,Column,05':            'i0 nA',
                     'XDI,Column,06':            'it nA',
                     'XDI,Column,07':            'ir nA'
                     }


class TC(Device):
    temperature = Cpt(EpicsSignal, 'T-I-I')

first_crystal  = TC('XF:06BMA-OP{Mono:DCM-Crys:1}',      name='first_crystal')
compton_shield = TC('XF:06BMA-OP{Mono:DCM-Crys:1-Ax:R}', name='compton_shield')


class Ring(Device):
        current    = Cpt(EpicsSignalRO, ':OPS-BI{DCCT:1}I:Real-I')
        lifetime   = Cpt(EpicsSignalRO, ':OPS-BI{DCCT:1}Lifetime-I')
        energy     = Cpt(EpicsSignalRO, '{}Energy_SRBend')
        mode       = Cpt(EpicsSignalRO, '-OPS{}Mode-Sts', string=True)
        filltarget = Cpt(EpicsSignalRO, '-HLA{}FillPattern:DesireImA')

ring = Ring('SR', name='ring')

## some heuristics for determining state of M2 and M3
def mirror_state():
    if m2.vertical.readback.value > 0:
        m2state = 'not in use'
    else:
        m2state = 'torroidal mirror, 5 nm Rh on 30 nm Pt, pitch = %.2f mrad, bender = %d counts' % (7.0 - m2.pitch.readback.value,
                                                                                                    int(m2_bender.user_readback.value))
    if m3.lateral.readback.value > 0:
        stripe =  'Pt stripe'
    else:
        stripe =  'Si stripe'
    if abs(m3.vertical.readback.value + 1.5) < 0.1:
        m3state = 'not in use'
    else:
        m3state = 'flat mirror, %s, pitch = %.1f mrad relative to beam' % (stripe, 7.0 - m2.pitch.readback.value)
    return(m2state, m3state)


def bmm_metadata(measurement   = 'transmission',
                 experimenters = '',
                 edge          = 'K',
                 element       = 'Fe',
                 edge_energy   = '7112',
                 direction     = 1,
                 scantype      = 'step',
                 channelcut    = True,
                 mono          = 'Si(111)',
                 i0_gas        = 'N2',
                 it_gas        = 'N2',
                 ir_gas        = 'N2',
                 sample        = 'Fe foil',
                 prep          = '',
                 stoichiometry = None,
                 mode          = 'transmission',
                 comment       = '',
                 ththth        = False,
                ):
    '''
    fill a dictionary with BMM-specific metadata.  this will be stored in the <db>.start['md'] field

    Argument list:
      measurement   -- 'transmission' or 'fluorescence'
      edge          -- 'K', 'L3', 'L2', or 'L1'
      element       -- one or two letter element symbol
      edge_energy   -- edge energy used to constructing scan parameters
      direction     -- 1/0/-1, 1 for increasing, -1 for decreasing, 0 for fixed energy
      scan          -- 'step' or 'slew'
      channelcut    -- True/False, False for fixed exit, True for pseudo-channel-cut
      mono          -- 'Si(111)' or 'Si(311)'
      i0_gas        -- a string using N2, He, Ar, and Kr
      it_gas        -- a string using N2, He, Ar, and Kr
      sample        -- one-line sample description
      prep          -- one-line explanation of sample preparation
      stoichiometry -- None or IUCr stoichiometry string
      mode          -- transmission, fluorescence, reference
      comment       -- user-supplied, free-form comment string
      ththth        -- True is measuring with the Si(333) relfection
    '''

    md                                = copy.deepcopy(bmm_metadata_stub)
    md['XDI,_mode']                   = mode,
    md['XDI,_comment']                = comment,
    md['XDI,_scantype']               = 'xafs step scan',
    if 'fixed' in scantype:
        md['XDI,_scantype']           = 'single-energy x-ray absorption detection',
    md['XDI,Element,edge']            = edge.capitalize()
    md['XDI,Element,symbol']          = element.capitalize()
    md['XDI,Scan,edge_energy']        = edge_energy
    md['XDI,Scan,experimenters']      = experimenters
    md['XDI,Mono,name']               = 'Si(%s)' % dcm._crystal
    md['XDI,Mono,d_spacing']          = '%.7f Å' % (dcm._twod/2)
    md['XDI,Mono,encoder_resolution'] = dcm.bragg.resolution.value
    md['XDI,Mono,angle_offset']       = dcm.bragg.user_offset.value
    md['XDI,Detector,I0']             = '10 cm ' + i0_gas
    md['XDI,Detector,It']             = '25 cm ' + it_gas
    md['XDI,Detector,Ir']             = '25 cm ' + ir_gas
    md['XDI,Facility,GUP']            = BMM_xsp.gup
    md['XDI,Facility,SAF']            = BMM_xsp.saf
    md['XDI,Sample,name']             = sample
    md['XDI,Sample,prep']             = prep
    #md['XDI,Sample,x_position']       = xafs_linx.user_readback.value
    #md['XDI,Sample,y_position']       = xafs_liny.user_readback.value
    #md['XDI,Sample,roll_position']    = xafs_roll.user_readback.value
    ## what about pitch, linxs, rotX ???
    if stoichiometry is not None:
        md['XDI,Sample,stoichiometry'] = stoichiometry

    if ththth:
        md['XDI,Mono,name']            = 'Si(333)'
        md['XDI,Mono,d_spacing']       = '%.7f Å' % (dcm._twod/6)
            
        
    (m2state, m3state) = mirror_state()
    md['XDI,Beamline,focusing'] = m2state
    md['XDI,Beamline,harmonic_rejection'] = m3state

    # if focus:
    #     md['XDI,Beamline,focusing'] = 'torroidal mirror with bender, 5 nm Rh on 30 nm Pt'
    # else:
    #     md['XDI,Beamline,focusing'] = 'none'

    # if hr:
    #     md['XDI,Beamline,harmonic_rejection'] = 'flat, Pt stripe; Si stripe below 8 keV'
    # else:
    #     md['XDI,Beamline,harmonic_rejection'] = 'none'

    if direction > 0:
        md['XDI,Mono,direction'] = 'increasing in energy'
    elif direction == 0:
        md['XDI,Mono,direction'] = 'fixed in energy'
    else:
        md['XDI,Mono,direction'] = 'decreasing in energy'

    if 'step' in scantype:
        md['XDI,Mono,scan_type'] = 'step'
    elif 'fixed' in scantype:
        md['XDI,Mono,scan_type'] = 'single energy'
    else:
        md['XDI,Mono,scan_type'] = 'slew'

    if channelcut is True:
        md['XDI,Mono,scan_mode'] = 'pseudo channel cut'
    else:
        md['XDI,Mono,scan_mode'] = 'fixed exit'

    if 'fluo' in measurement or 'flou' in measurement or 'both' in measurement:
        md['XDI,Detector,fluorescence'] = 'SII Vortex ME4 (4-element silicon drift)'
        md['XDI,Detector,deadtime_correction'] = 'DOI: 10.1107/S0909049510009064'

    if 'yield' in measurement:
        md['XDI,Detector,yield'] = 'simple electron yield detector with batteries and He'

    return md

def metadata_at_this_moment():
    '''Gather the sort of scan metadata that could change between scans
    in a scan sequence.  Return a dictionary.

    '''
    rightnow = dict()
    #rightnow['XDI,Mono,first_crystal_temperature']  = float(first_crystal.temperature.value)
    #rightnow['XDI,Mono,compton_shield_temperature'] = float(compton_shield.temperature.value)
    #rightnow['XDI,Facility,current']  = str(ring.current.value) + ' mA'
    try:
        rightnow['XDI,Facility,energy']   = str(round(ring.energy.value/1000., 1)) + ' GeV'
        rightnow['XDI,Facility,mode']     = ring.mode.value
    except:
        rightnow['XDI,Facility,energy']   = '0 GeV'
        rightnow['XDI,Facility,mode']     = 'Maintenance'
    if rightnow['XDI,Facility,mode'] == 'Operations':
        rightnow['XDI,Facility,mode'] = 'top-off'
    return rightnow
