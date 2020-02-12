from ophyd import QuadEM, Component as Cpt, EpicsSignalWithRBV, Signal, DerivedSignal, EpicsSignal
from ophyd.quadem import QuadEMPort

from numpy import log, exp

run_report(__file__)

## need to do something like this:
##    caput XF:06BM-BI{EM:1}EM180:Current3:MeanValue_RBV.PREC 7
## to get a sensible reporting precision from the Ix channels


class Nanoize(DerivedSignal):
    def forward(self, value):
        return value * 1e-9 / _locked_dwell_time.dwell_time.readback.value
    def inverse(self, value):
        return value * 1e9 * _locked_dwell_time.dwell_time.readback.value

# class Normalized(DerivedSignal):
#     def forward(self, value):
#         return value * self.parent.current1.mean_value.value
#     def inverse(self, value):
#         return value / self.parent.current1.mean_value.value

# class TransXmu(DerivedSignal):
#     def forward(self, value):
#         return self.parent.current1.mean_value.value / exp(value)
#     def inverse(self, value):
#         arg = self.parent.current1.mean_value.value / value
#         return log(abs(arg))

class BMMQuadEM(QuadEM):
    _default_read_attrs = ['I0',
                           'It',
                           'Ir',
                           'Iy']
    port_name = Cpt(Signal, value='EM180')
    conf = Cpt(QuadEMPort, port_name='EM180')
    em_range  = Cpt(EpicsSignalWithRBV, 'Range', string=True)
    I0 = Cpt(Nanoize, derived_from='current1.mean_value')
    It = Cpt(Nanoize, derived_from='current2.mean_value')
    Ir = Cpt(Nanoize, derived_from='current3.mean_value')
    Iy = Cpt(Nanoize, derived_from='current4.mean_value')
    #iti0   = Cpt(Normalized, derived_from='current2.mean_value')
    #lni0it = Cpt(TransXmu,   derived_from='current2.mean_value')
    state  = Cpt(EpicsSignal, 'Acquire')
    #  = Cpt(EpicsSignal, 'PREC')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #for c in ['current{}'.format(j) for j in range(1, 5)]:
        #     getattr(self, c).read_attrs = ['mean_value']

        # self.read_attrs = ['current{}'.format(j) for j in range(1, 5)]
        self._acquisition_signal = self.acquire
        self.configuration_attrs = ['integration_time', 'averaging_time','em_range','num_averaged','values_per_read']

    def on(self):
        print('Turning {} on'.format(self.name))
        self.acquire_mode.put(0)
        self.acquire.put(1)

    def off(self):
        print('Turning {} off'.format(self.name))
        self.acquire_mode.put(2)
        self.acquire.put(0)

    def on_plan(self):
        yield from abs_set(self.acquire, 1, wait=True)
        yield from abs_set(self.acquire_mode, 0, wait=True)

    def off_plan(self):
        yield from abs_set(self.acquire, 0, wait=True)
        yield from abs_set(self.acquire_mode, 2, wait=True)


        
quadem1 = BMMQuadEM('XF:06BM-BI{EM:1}EM180:', name='quadem1')

def set_precision(pv, val):
    EpicsSignal(pv.pvname + ".PREC", name='').put(val)

set_precision(quadem1.current1.mean_value, 3)
toss = quadem1.I0.describe()
set_precision(quadem1.current2.mean_value, 3)
toss = quadem1.It.describe()
set_precision(quadem1.current3.mean_value, 3)
toss = quadem1.Ir.describe()
set_precision(quadem1.current4.mean_value, 3)
toss = quadem1.Iy.describe()


quadem1.I0.kind = 'hinted'
quadem1.It.kind = 'hinted'
quadem1.Ir.kind = 'hinted'
quadem1.Iy.kind = 'omitted'      # 'hinted'

quadem1.I0.name = 'I0'
quadem1.It.name = 'It'
quadem1.Ir.name = 'Ir'
quadem1.Iy.name = 'Iy'


#quadem1.current4_mean_value_nano.kind = 'omitted'


class BMMDualEM(QuadEM):
    _default_read_attrs = ['Ia',
                           'Ib']
    port_name = Cpt(Signal, value='NSLS2_IC')
    conf = Cpt(QuadEMPort, port_name='NSLS2_IC')
    em_range = Cpt(EpicsSignalWithRBV, 'Range', string=True)
    Ia = Cpt(Nanoize, derived_from='current1.mean_value')
    Ib = Cpt(Nanoize, derived_from='current2.mean_value')
    state = Cpt(EpicsSignal, 'Acquire')

    calibration_mode = Cpt(EpicsSignal, 'CalibrationMode')
    copy_adc_offsets = Cpt(EpicsSignal, 'CopyADCOffsets.PROC')
    compute_current_offset1 = Cpt(EpicsSignal, 'ComputeCurrentOffset1.PROC')
    compute_current_offset2 = Cpt(EpicsSignal, 'ComputeCurrentOffset2.PROC')

    sigma1 = Cpt(EpicsSignal, 'Current1:Sigma_RBV')
    sigma2 = Cpt(EpicsSignal, 'Current1:Sigma_RBV')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #for c in ['current{}'.format(j) for j in range(1, 5)]:
        #     getattr(self, c).read_attrs = ['mean_value']

        # self.read_attrs = ['current{}'.format(j) for j in range(1, 5)]
        self._acquisition_signal = self.acquire
        self.configuration_attrs = ['integration_time', 'averaging_time','em_range','num_averaged','values_per_read']

    def on(self):
        print('Turning {} on'.format(self.name))
        self.acquire_mode.put(0)
        self.acquire.put(1)

    def off(self):
        print('Turning {} off'.format(self.name))
        self.acquire_mode.put(2)
        self.acquire.put(0)

    def on_plan(self):
        yield from abs_set(self.acquire, 1, wait=True)
        yield from abs_set(self.acquire_mode, 0, wait=True)

    def off_plan(self):
        yield from abs_set(self.acquire, 0, wait=True)
        yield from abs_set(self.acquire_mode, 2, wait=True)

    def dark_current(self):
        reopen = shb.state.value == shb.openval 
        if reopen:
            print('\nClosing photon shutter')
            yield from shb.close_plan()
        print('Measuring current offsets, this will take several seconds')

        ## this almost works....

        self.current_offsets.ch1.put(0.0)
        self.current_offsets.ch2.put(0.0)
        self.calibration_mode.put(1)
        yield from sleep(0.5)
        self.copy_adc_offsets.put(1)
        yield from sleep(0.5)
        self.calibration_mode.put(0)
        yield from sleep(0.5)
        self.compute_current_offset1.put(1)
        self.compute_current_offset1.put(2)
        # EpicsSignal("XF:06BM-BI{EM:3}EM180:CopyADCOffsets.PROC", name='').put(1)
        # EpicsSignal("XF:06BM-BI{EM:3}EM180:CalibrationMode", name='').put(0)
        # EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset1.PROC", name='').put(1)
        # EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset2.PROC", name='').put(1)
        yield from sleep(0.5)
        print(self.sigma1.value, self.sigma2.value)
        BMM_log_info('Measured dark current on dualio ion chamber')
        if reopen:
            print('Opening photon shutter')
            yield from shb.open_plan()
            print('You are ready to measure!\n')

        
# dualio = BMMDualEM('XF:06BM-BI{EM:3}EM180:', name='DualI0')
# dualio.Ia.kind = 'hinted'
# dualio.Ib.kind = 'hinted'
# dualio.Ia.name = 'Ia'
# dualio.Ib.name = 'Ib'



quadem2 = QuadEM('XF:06BM-BI{EM:2}EM180:', name='quadem2')


def dark_current():
    reopen = shb.state.value == shb.openval 
    if reopen:
        print('\nClosing photon shutter')
        yield from shb.close_plan()
    print('Measuring current offsets, this will take several seconds')
    EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset1.PROC", name='').put(1)
    EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset2.PROC", name='').put(1)
    EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset3.PROC", name='').put(1)
    EpicsSignal("XF:06BM-BI{EM:1}EM180:ComputeCurrentOffset4.PROC", name='').put(1)
    yield from sleep(3)
    BMM_log_info('Measured dark current on quadem1')
    if reopen:
        print('Opening photon shutter')
        yield from shb.open_plan()
        print('You are ready to measure!\n')

    
