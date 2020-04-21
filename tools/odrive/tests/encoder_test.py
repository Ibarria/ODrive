
import test_runner

import time
from math import pi
import os

from fibre.utils import Logger
from test_runner import *


teensy_code_template = """
void setup() {
  pinMode({enc_a}, OUTPUT);
  pinMode({enc_b}, OUTPUT);
}

int cpr = 8192;
int rpm = 30;

// the loop routine runs over and over again forever:
void loop() {
  int microseconds_per_count = (1000000 * 60 / cpr / rpm);

  for (;;) {
    digitalWrite({enc_a}, HIGH);
    delayMicroseconds(microseconds_per_count);
    digitalWrite({enc_b}, HIGH);
    delayMicroseconds(microseconds_per_count);
    digitalWrite({enc_a}, LOW);
    delayMicroseconds(microseconds_per_count);
    digitalWrite({enc_b}, LOW);
    delayMicroseconds(microseconds_per_count);
  }
}

"""


class TestIncrementalEncoder():

    def get_test_cases(self, testrig: TestRig):
        for odrive in testrig.get_components(ODriveComponent):
            for encoder in odrive.encoders:
                # Find the Teensy that is connected to the encoder pins and the corresponding Teensy GPIOs

                gpio_conns = [
                    testrig.get_directly_connected_components(encoder.a),
                    testrig.get_directly_connected_components(encoder.b),
                ]

                valid_combinations = [
                    [combination[0].parent] + list(combination)
                    for combination in itertools.product(*gpio_conns)
                    if ((len(set(c.parent for c in combination)) == 1) and isinstance(combination[0].parent, TeensyComponent))
                ]

                yield (encoder, valid_combinations)

    def run_delta_test(self, encoder, true_cps, with_cpr):
        encoder.config.cpr = with_cpr

        for i in range(100):
            now = time.monotonic()
            new_shadow_count = encoder.shadow_count
            new_count_in_cpr = encoder.count_in_cpr
            new_phase = encoder.phase
            new_pos_estimate = encoder.pos_estimate
            new_pos_cpr = encoder.pos_cpr

            if i > 0:
                dt = now - before
                test_assert_eq((new_shadow_count - last_shadow_count) / dt, true_cps, accuracy = 0.05)
                test_assert_eq(modpm(new_count_in_cpr - last_count_in_cpr, with_cpr) / dt, true_cps, accuracy = 0.3)
                #test_assert_eq(modpm(new_phase - last_phase, 2*pi) / dt, 2*pi*true_rps, accuracy = 0.1)
                test_assert_eq((new_pos_estimate - last_pos_estimate) / dt, true_cps, accuracy = 0.3)
                test_assert_eq(modpm(new_pos_cpr - last_pos_cpr, with_cpr) / dt, true_cps, accuracy = 0.3)
                test_assert_eq(encoder.vel_estimate, true_cps, accuracy = 0.05)
 
            before = now
            last_shadow_count = new_shadow_count
            last_count_in_cpr = new_count_in_cpr
            last_phase = new_phase
            last_pos_estimate = new_pos_estimate
            last_pos_cpr = new_pos_cpr
 
            time.sleep(0.01)

    def run_test(self, enc: EncoderComponent, teensy: TeensyComponent, teensy_gpio_a: int, teensy_gpio_b: int, logger: Logger):
        true_cps = 8192*-0.5 # counts per second generated by the virtual encoder
        
        code = teensy_code_template.replace("{enc_a}", str(teensy_gpio_a.num)).replace("{enc_b}", str(teensy_gpio_b.num))
        teensy.compile_and_program(code)

        time.sleep(1.0) # wait for PLLs to stabilize

        encoder = enc.handle

        # The true encoder count and PLL output should be roughly the same.
        # At 8192 CPR and 0.5 RPM, the delta because of sequential reading is
        # around 3.25 counts. The exact value depends on the connection.
        # The tracking error of the PLL is below 1 count.

        #logger.debug("check if count_in_cpr == pos_cpr")
        #configured_cpr = 8192
        #encoder.config.cpr = configured_cpr
        #expected_delta = true_cps/1200
        #for _ in range(1000):
        #    first = enc.handle.axis0.encoder.count_in_cpr
        #    second = enc.handle.axis0.encoder.pos_cpr
        #    test_assert_eq(modpm(second - first, configured_cpr), expected_delta, range=abs(true_cps/500))
        #    time.sleep(0.001)

        logger.debug("check if variables move at the correct velocity (8192 CPR)...")
        self.run_delta_test(encoder, true_cps, 8192)
        logger.debug("check if variables move at the correct velocity (65536 CPR)...")
        self.run_delta_test(encoder, true_cps, 65536)
        encoder.config.cpr = 8192



if __name__ == '__main__':
    test_runner.run(TestIncrementalEncoder())
