# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Integration code for FishFuzz_AFL fuzzer."""

import json
import os
import shutil
import subprocess
import sys

from fuzzers import utils

def find_files(filename, search_path, mode):
    """Helper function to find path of TEMP, mode 0 for file and 1 for dir"""
    result = ''
    for root, dir, files in os.walk(search_path):
        if mode == 0:
            if filename in files:
                # result.append(os.path.join(root, filename))
                return os.path.join(root, filename)
        else:
            if filename in dir:
                return os.path.join(root, filename)
    return result

def prepare_build_environment():
    """Set environment variables used to build targets for AFL-based
    fuzzers."""

    build_directory = os.environ['OUT']

    cflags = ['-fsanitize=address']
    utils.append_flags('CFLAGS', cflags)
    utils.append_flags('CXXFLAGS', cflags)

    os.environ['CC'] = '/FishFuzz/ff-all-in-one'
    os.environ['CXX'] = '/FishFuzz/ff-all-in-one++'
    os.environ['FF_DRIVER_NAME'] = os.getenv('FUZZ_TARGET')
    os.environ['FUZZER_LIB'] = '/libAFL.a'

    os.environ['AFL_QUIET'] = '1'
    os.environ['AFL_LLVM_DICT2FILE'] = build_directory + '/afl++.dict'
    os.environ['AFL_LLVM_DICT2FILE_NO_MAIN'] = '1'
    os.environ['AFL_LLVM_USE_TRACE_PC'] = '1'


def get_cmplog_build_directory(target_directory):
    """Return path to CmpLog target directory."""
    return os.path.join(target_directory, 'cmplog')


def build():
    """Build benchmark."""
    prepare_build_environment()

    #with utils.restore_directory(src), utils.restore_directory(work):
    utils.build_benchmark()

    print('[post_build] Copying afl-fuzz to $OUT directory')
    # Copy out the afl-fuzz binary as a build artifact.
    shutil.copy('/FishFuzz/afl-fuzz', os.environ['OUT'])
    print(os.environ['FF_DRIVER_NAME'])
    os.environ['AFL_CC'] = 'clang-12'
    os.environ['AFL_CXX'] = 'clang++-12'
    bin_fuzz_dst = '%s/%s' % (os.environ['OUT'], os.environ['FF_DRIVER_NAME'])
    bin_fuzz_src = find_files('%s.fuzz' % (os.environ['FF_DRIVER_NAME']), '/', 0)
    os.system("find / -name '*" + os.environ['FF_DRIVER_NAME'] + "*' > /dev/null")
    if bin_fuzz_src:
        shutil.copy(bin_fuzz_src, bin_fuzz_dst)
    else:
        print('NOT FOUND: ' + '%s.fuzz' % (os.environ['FF_DRIVER_NAME']))
        sys.exit(1)
    tmp_dir_dst = '%s/TEMP' % (os.environ['OUT'])
    tmp_dir_src = find_files('TEMP_%s' % (os.environ['FF_DRIVER_NAME']), '/', 1)
    print('TEMP_%s' % (os.environ['FF_DRIVER_NAME']))
    print(tmp_dir_dst)
    print('that was second')
    #for tmp_dir_src in foo:
    if tmp_dir_src:
        print(tmp_dir_src)
        print(tmp_dir_dst)
        shutil.copytree(tmp_dir_src, tmp_dir_dst)
    else:
        print('NOT FOUND: ' + 'TEMP_%s' % (os.environ['FF_DRIVER_NAME']))
        sys.exit(1)
    print('done')

#    src = os.getenv('SRC')
#    work = os.getenv('WORK')
#
    #with utils.restore_directory(src), utils.restore_directory(work):
    #    # CmpLog requires an build with different instrumentation.
    #    new_env = os.environ.copy()
    #    new_env['AFL_LLVM_CMPLOG'] = '1'
#
#        # For CmpLog build, set the OUT and FUZZ_TARGET environment
#        # variable to point to the new CmpLog build directory.
#        build_directory = os.environ['OUT']
#        #cmplog_build_directory = get_cmplog_build_directory(build_directory)
#        #os.mkdir(cmplog_build_directory)
#        new_env['OUT'] = cmplog_build_directory
#        fuzz_target = os.getenv('FUZZ_TARGET')
#        if fuzz_target:
#            new_env['FUZZ_TARGET'] = os.path.join(cmplog_build_directory,
#                                                  os.path.basename(fuzz_target))
#
#        print('Re-building benchmark for CmpLog fuzzing target')
#        utils.build_benchmark(env=new_env)



def get_stats(output_corpus, fuzzer_log):  # pylint: disable=unused-argument
    """Gets fuzzer stats for AFL."""
    # Get a dictionary containing the stats AFL reports.
    stats_file = os.path.join(output_corpus, 'fuzzer_stats')
    if not os.path.exists(stats_file):
        print('Can\'t find fuzzer_stats')
        return '{}'
    with open(stats_file, encoding='utf-8') as file_handle:
        stats_file_lines = file_handle.read().splitlines()
    stats_file_dict = {}
    for stats_line in stats_file_lines:
        key, value = stats_line.split(': ')
        stats_file_dict[key.strip()] = value.strip()

    # Report to FuzzBench the stats it accepts.
    stats = {'execs_per_sec': float(stats_file_dict['execs_per_sec'])}
    return json.dumps(stats)


def prepare_fuzz_environment(input_corpus):
    """Prepare to fuzz with AFL or another AFL-based fuzzer."""
    # Tell AFL to not use its terminal UI so we get usable logs.
    os.environ['AFL_NO_UI'] = '1'
    # Skip AFL's CPU frequency check (fails on Docker).
    os.environ['AFL_SKIP_CPUFREQ'] = '1'
    # No need to bind affinity to one core, Docker enforces 1 core usage.
    os.environ['AFL_NO_AFFINITY'] = '1'
    # AFL will abort on startup if the core pattern sends notifications to
    # external programs. We don't care about this.
    os.environ['AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES'] = '1'
    # Don't exit when crashes are found. This can happen when corpus from
    # OSS-Fuzz is used.
    os.environ['AFL_SKIP_CRASHES'] = '1'
    # Shuffle the queue
    #os.environ['AFL_SHUFFLE_QUEUE'] = '1'

    # Set temporary dir path
    tmp_dir_src = '%s/TEMP' % (os.environ['OUT'])
    os.environ['TMP_DIR'] = tmp_dir_src

    # AFL needs at least one non-empty seed to start.
    utils.create_seed_file_for_empty_corpus(input_corpus)


def run_afl_fuzz(input_corpus,
                 output_corpus,
                 target_binary,
                 additional_flags=None,
                 hide_output=False):
    """Run afl-fuzz."""
    # Spawn the afl fuzzing process.

    os.environ['AFL_IGNORE_UNKNOWN_ENVS'] = '1'
    os.environ['AFL_FAST_CAL'] = '1'
    os.environ['AFL_NO_WARN_INSTABILITY'] = '1'
    os.environ['AFL_DISABLE_TRIM'] = '1'
    os.environ['AFL_CMPLOG_ONLY_NEW'] = '1'

    target_binary_directory = os.path.dirname(target_binary)
    cmplog_target_binary_directory = (
        get_cmplog_build_directory(target_binary_directory))
    target_binary_name = os.path.basename(target_binary)
    cmplog_target_binary = os.path.join(cmplog_target_binary_directory,
                                        target_binary_name)

    print('[run_afl_fuzz] Running target with afl-fuzz')
    command = [
        './afl-fuzz',
        '-i',
        input_corpus,
        '-o',
        output_corpus,
        '-t',
        '1000+',  # Use same default 1 sec timeout, but add '+' to skip hangs.
    ]

    if additional_flags:
        command.extend(additional_flags)

    dictionary_path = utils.get_dictionary_path(target_binary)
    if dictionary_path:
        command.extend(['-x', dictionary_path])

    flags += ['-x', './afl++.dict']

    #flags += ['-c', cmplog_target_binary]

    command += [
        '--',
        target_binary,
        # Pass INT_MAX to afl the maximize the number of persistent loops it
        # performs.
        '2147483647'
    ]
    print('[run_afl_fuzz] Running command: ' + ' '.join(command))
    output_stream = subprocess.DEVNULL if hide_output else None
    subprocess.check_call(command, stdout=output_stream, stderr=output_stream)


def fuzz(input_corpus, output_corpus, target_binary):
    """Run afl-fuzz on target."""
    
    print('FUZZ!!!')
    
    prepare_fuzz_environment(input_corpus)

    run_afl_fuzz(input_corpus, output_corpus, target_binary)
