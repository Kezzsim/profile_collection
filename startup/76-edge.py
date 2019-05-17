import time
import json

run_report(__file__)

class ReferenceFoils():
    '''A simple class for managing the reference foil holder.

    Configure reference holder:
       foils.set('Mn Fe Cu Zn Pb')

    Configure one slot of the reference holder:
       foils.set_slot(2, 'Fe')

    Return the xafs_ref value for a slot:
       pos = foils.position(2)

    Move to a slot by element symbol:
       RE(foils.move('Fe'))
       yield from foils.move('Fe')

    Print foils configuration to the screen:
       foils.show()
    '''
    def __init__(self):
        self.slots = [None, None, None, None, None]

    def unset(self):
        self.slots = [None, None, None, None, None]
        jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
        if os.path.isfile(jsonfile):
            user = json.load(open(jsonfile))
            if 'foils' in user:
                del user['foils']
                os.chmod(jsonfile, 0o644)
                with open(jsonfile, 'w') as outfile:
                    json.dump(user, outfile)
                os.chmod(jsonfile, 0o444)

    def set_slot(self, i, el):
        '''Configure a slot i ∈ (0 .. 4) for element el'''
        if Z_number(el) is None:        
            self.slots[i-1] = None
        else:
            self.slots[i-1] = element_symbol(el)
        BMM_log_info('Set reference slot %d to %s' % (i, str(self.slots[i-1])))

    def set(self, elements):
        '''Configure the foils so that an energy change knows where to put the
        reference stage.

        Input:
          elements: a list of 5 foils, top to bottom in the foil holder
                    if the list is a space separated string, it will be split into a list
        '''
        if type(elements) is str:
            elements = elements.split()
        if len(elements) != 5:
            print(error_msg('\nThe list of foils must have five elements\n'))
            return()
        for i in range(5):
            self.set_slot(i+1, elements[i])
        self.show()
        #########################################################
        # save the foil configuration to the user serialization #
        #########################################################
        jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
        user = dict()
        if os.path.isfile(jsonfile):
            user = json.load(open(jsonfile))
            user['foils'] = ' '.join(map(str, elements))
            os.chmod(jsonfile, 0o644)
        with open(jsonfile, 'w') as outfile:
            json.dump(user, outfile)
        os.chmod(jsonfile, 0o444)
            
        
    def position(self, i):
        '''Return the xafs_ref position corresponding to slot i where i ∈ (0 .. 4)'''
        if type(i) is not int: return xafs_ref.user_readback.value # so it doesn't move...
        if i > 4:        return 90
        if i < 0:        return -90
        return(-90 + i*45)

    def move(self, el):
        '''Move to the slot configured for element el'''
        if type(el) is int:
            if el < 1 or el > 5:
                print(error_msg('\n%d is not a valid foil slot\n' % el))
                return(yield from null())
            el = self.slots[el-1]
        if el is None:
            print(error_msg('\nThat slot is empty\n'))
            return(yield from null())
        if Z_number(el) is None:
            print(error_msg('\n%s is not an element\n' % el))
            return(yield from null())
        moved = False
        for i in range(5):
            if element_symbol(el) == self.slots[i]:
                yield from mv(xafs_ref, self.position(i))
                report('Moved xafs_ref to %s at slot %d' % (el.capitalize(), i+1))
                moved = True
        if not moved:
            print(warning_msg('%s is not in the reference holder, not moving xafs_ref' % el.capitalize()))
            yield from null()
            
    def show(self):
        '''Show configuration of foil holder'''
        print('Reference foils (xafs_ref):')
        for i in range(5):
            print('\tslot %d : %s at %d mm'% (i+1, str(self.slots[i]), self.position(i)))
            
foils = ReferenceFoils()
## if this startup file is "%run -i"-ed, then need to reset
## foils to the serialized configuration
jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
if os.path.isfile(jsonfile):
    user = json.load(open(jsonfile))
    if 'foils' in user:
        foils.set(user['foils'])
## else if starting bsui fresh, perform the delayed foil configuration
if BMMuser.read_foils is not None:
    foils.set(BMMuser.read_foils)
    BMMuser.read_foils = None



class ROI():
    '''A simple class for managing the Struck ROI channels.
    '''
    def __init__(self):
        self.slots = [None, None, None]

    def unset(self):
        self.slots = [None, None, None]
        jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
        if os.path.isfile(jsonfile):
            user = json.load(open(jsonfile))
            if 'rois' in user:
                del user['rois']
                os.chmod(jsonfile, 0o644)
                with open(jsonfile, 'w') as outfile:
                    json.dump(user, outfile)
                os.chmod(jsonfile, 0o444)
    
    def set_roi(self, i, el):
        '''Configure an ROI channel i ∈ (1 .. 3) for element el'''
        if Z_number(el) is None:
            self.slots[i-1] = None
        else:
            self.slots[i-1] = element_symbol(el)
        BMM_log_info('Set ROI channel %d to %s' % (i, str(self.slots[i-1])))

    def set(self, elements):
        '''Configure the ROI channels so that an energy change knows which channel to use.

        Input:
          elements: a list of 3 elements, top to bottom in the SCAs
                    if the list is a space separated string, it will be split into a list
        '''
        if type(elements) is str:
            elements = elements.split()
        if len(elements) != 3:
            print(error_msg('\nThe list of foils must have three elements\n'))
            return()
        for i in range(3):
            self.set_roi(i+1, elements[i])
        self.show()
        ########################################################
        # save the ROI configuration to the user serialization #
        ########################################################
        jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
        user = dict()
        if os.path.isfile(jsonfile):
            user = json.load(open(jsonfile))
        user['rois'] = ' '.join(map(str, elements))
        os.chmod(jsonfile, 0o644)
        with open(jsonfile, 'w') as outfile:
            json.dump(user, outfile)
        os.chmod(jsonfile, 0o444)

    def select(self, el):
        '''Choose the ROI configured for element el'''
        if type(el) is int:
            if el < 1 or el > 3:
                print(error_msg('\n%d is not a valid ROI channel\n' % el))
                return(yield from null())
            el = self.slots[el-1]
        if el is None:
            print(error_msg('\nThat ROI is not configured\n'))
            return(yield from null())
        if Z_number(el) is None:
            print(error_msg('\n%s is not an element\n' % el))
            return(yield from null())
        selected = False
        for i in range(3):
            if element_symbol(el) == self.slots[i]:
                BMMuser.roi_channel = i+1
                if i == 0:      # help out the best effort callback
                    (BMMuser.roi1, BMMuser.roi2, BMMuser.roi3, BMMuser.roi4) = ('ROI1', 'ROI2', 'ROI3', 'ROI4')
                    (BMMuser.dtc1, BMMuser.dtc2, BMMuser.dtc3, BMMuser.dtc4) = ('DTC1', 'DTC2', 'DTC3', 'DTC4')
                    vor.set_hints(1)
                elif i == 1:
                    (BMMuser.roi1, BMMuser.roi2, BMMuser.roi3, BMMuser.roi4) = ('ROI2.1', 'ROI2.2', 'ROI2.3', 'ROI2.4')
                    (BMMuser.dtc1, BMMuser.dtc2, BMMuser.dtc3, BMMuser.dtc4) = ('DTC2.1', 'DTC2.2', 'DTC2.3', 'DTC2.4')
                    vor.set_hints(2)
                elif i == 2:
                    (BMMuser.roi1, BMMuser.roi2, BMMuser.roi3, BMMuser.roi4) = ('ROI3.1', 'ROI3.2', 'ROI3.3', 'ROI3.4')
                    (BMMuser.dtc1, BMMuser.dtc2, BMMuser.dtc3, BMMuser.dtc4) = ('DTC3.1', 'DTC3.2', 'DTC3.3', 'DTC3.4')
                    vor.set_hints(3)
                report('Set ROI channel to %s at channel %d' % (el.capitalize(), i+1))
                selected = True
        if not selected:
            print(warning_msg('%s is not in a configured channel, not changing BMMuser.roi_channel' % el.capitalize()))
            yield from null()
        
    def show(self):
        '''Show configuration of ROI channels'''
        print('ROI channels:')
        for i in range(3):
            print('\tROI %d : %s'% (i+1, str(self.slots[i])))

rois = ROI()
## if this startup file is "%run -i"-ed, then need to reset
## foils to the serialized configuration
jsonfile = os.path.join(os.environ['HOME'], 'Data', '.user.json')
if os.path.isfile(jsonfile):
    user = json.load(open(jsonfile))
    if 'rois' in user:
        rois.set(user['rois'])
        BMMuser.read_rois = None
## else if starting bsui fresh, perform the delayed foil configuration
if BMMuser.read_rois is not None:
    rois.set(BMMuser.read_rois)
    BMMuser.read_foils = None



        

    
def approximate_pitch(energy):
    if dcm._crystal is '111':
        m = -4.42156e-6
        b = 3.94956
        return(m*energy + b)
    else:
        m = -4.42156e-6
        b = 3.94956
        return(dcm_pitch.user_readback.value)
        

def change_edge(el, focus=False, edge='K', energy=None, slits=True, calibrating=False, target=300.):
    '''Change edge energy by:
       1. Moving the DCM above the edge energy
       2. Moving the photon delivery system to the correct mode
       3. Running a rocking curve scan
       4. --(Running a slits_height scan)--
       5. Moving the reference holder to the correct slot

    Input:
       el:     (string) one- or two-letter symbol
       focus:  (Boolean) T=focused or F=unfocused beam         [False, unfocused]
       edge:   (string) edge symbol                            ['K']
       energy: (float) e0 value                                [None, determined from el/edge]
       slits:  (Boolean) perform slit_height() scan            [False]
       calibrating: (Boolean) skip change_mode() plan          [False]
       target: (float) energy where rocking curve is measured  [300]
    '''
    if energy is None:
        energy = edge_energy(el,edge)
        
    if energy is None:
        print(error_msg('\nEither %s or %s is not a valid symbol\n' % (el, edge)))
        return(yield from null())
    if energy > 23500:
        edge = 'L3'
        energy = edge_energy(el,'L3')

    if energy < 4950:
        print(warning_msg('The %s edge energy is below 4950 eV' % el))
        print(warning_msg('You have to change energy by hand.'))
        return(yield from null())

    if energy > 23500:
        print(warning_msg('The %s edge energy is outside the range of this beamline!' % el))
        return(yield from null())

    BMMuser.edge        = edge
    BMMuser.element     = el
    BMMuser.edge_energy = energy

    if energy > 8000:
        mode = 'A' if focus else 'D'
    elif energy < 6000:
        mode = 'B' if focus else 'F'
    else:
        mode = 'C' if focus else 'E'
    current_mode = get_mode()

    #########################
    # confirm energy change #
    #########################
    print(bold_msg('\nEnergy change:'))
    print('   %s: %s %s' % (list_msg('edge'),                    el.capitalize(), edge.capitalize()))
    print('   %s: %.1f'  % (list_msg('edge energy'),             energy))
    print('   %s: %.1f'  % (list_msg('target energy'),           energy+target))
    print('   %s: %s'    % (list_msg('focus'),                   str(focus)))
    print('   %s: %s'    % (list_msg('photon delivery mode'),    mode))
    print('   %s: %s'    % (list_msg('optimizing slits height'), str(slits)))
    if BMMuser.prompt:
        action = input("\nBegin energy change? [Y/n then Enter] ")
        if action.lower() == 'q' or action.lower() == 'n':
            return(yield from null())

    
    start = time.time()
    BMM_log_info('Configuring beamline for %s edge' % el)
    ###################################
    # move the DCM to target eV above #
    ###################################
    print('Moving mono to energy %.1f eV...' % (energy+target))
    yield from mv(dcm.energy, energy+target)

    ##############################################
    # change to the correct photon delivery mode #
    ##############################################
    if not calibrating and mode != current_mode:
        print('Moving to photon delivery mode %s...' % mode)
        yield from change_mode(mode=mode, prompt=False)

    ############################
    # run a rocking curve scan #
    ############################
    print('Optimizing rocking curve...')
    yield from abs_set(dcm_pitch.kill_cmd, 1)
    yield from mv(dcm_pitch, approximate_pitch(energy+target))
    yield from sleep(1)
    yield from abs_set(dcm_pitch.kill_cmd, 1)
    yield from rocking_curve()
    close_last_plot()
    
    ##########################
    # run a slits height scan #
    ##########################
    if slits:
        print('Optimizing slits height...')
        yield from slit_height(move=True)
        close_last_plot()
        ## redo rocking curve?

    ##############################################################
    # move to the correct reference slot & set reference channel #
    ##############################################################
    print('Moving reference foil...')
    yield from foils.move(el)
    rois.select(el)
    
    
    print('\nYou are now ready to measure at the %s edge' % el)
    print('\nSome things are not done automagically:')
    if slits is False:
        print('  * You may need to verify the slit position:  RE(slit_height())')
    print('  * If measuring fluorescence, be sure that there is a channel for %s' % el)
    BMM_log_info('Finished configuring for %s edge' % el)
    end = time.time()
    print('\n\nTime elapsed: %.1f min' % ((end-start)/60))
    return()
