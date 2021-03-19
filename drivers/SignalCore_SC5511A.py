from typing import Any, Dict, Optional

from qcodes import Instrument
from qcodes.utils.validators import Numbers

class SC5511A(Instrument):
    def __init__(self, name: str, s_n: str, **kwargs: Any):
        super().__init__(name, **kwargs)
        self.add_parameter('power',
                           label='Power',
                           get_cmd=self._get_power,
                           get_parser=float,
                           set_cmd=self._set_power,
                           unit='dBm',
                           vals=Numbers(min_value=-144,max_value=19))

    def _get_power(self):
        print("getting power")
        return 12

    def _set_power(self, pwr):
        print("setting power", pwr)
        return 1


        # self.add_parameter('frequency',
        #                    label='Frequency',
        #                    get_cmd='SOUR:FREQ?',
        #                    get_parser=float,
        #                    set_cmd='SOUR:FREQ {:.2f}',
        #                    unit='Hz',
        #                    vals=Numbers(min_value=9e3,max_value=max_freq))
        #
        # self.add_parameter('phase_offset',
        #                    label='Phase Offset',
        #                    get_cmd='SOUR:PHAS?',
        #                    get_parser=float,
        #                    set_cmd='SOUR:PHAS {:.2f}',
        #                    unit='rad'
        #                    )
        #
        # self.add_parameter('rf_output',
        #                    get_cmd='OUTP:STAT?',
        #                    set_cmd='OUTP:STAT {}',
        #                    val_mapping={'on': 1, 'off': 0})

        self.connect_message()

