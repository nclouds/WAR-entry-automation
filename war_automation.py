#!/usr/bin/env python

""" Selenium Automation Script for entering information into AWS WAR (Well-Architected Review) Portal
    
    Exit Codes:
        1 - Selenium is not installed
        2 - Selenium driver for Chrome browser is not installed
        3 - Error occurred during the initial setup
        4 - Invalid content in the input ini file
        5 - Login failed
        6 - Error during automation

    Script Version: N/A (Under development)
"""

import os, sys
import time, datetime, random
import logging
import argparse
from subprocess import Popen, PIPE
if 3 <= sys.version_info[0]:
    import configparser
else:
    import ConfigParser as configparser
try:
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException
except ModuleNotFoundError:
    print('Selenium is not installed.\n\nFor installation run the following command: ' + \
           'pip install selenium\nFor more details visit: https://pypi.org/project/selenium/')
    exit(1)
except Exception as err:
    print(str(err))
    exit(1)

# TODO update the info
script_version = "N/A (Under development)" 
args = None

def logging_setup(log_file_path):
    logging.basicConfig(filename = log_file_path, format = '%(asctime)s %(message)s', 
                        level=logging.DEBUG)

def run_command(command_str):
    try:
        process = Popen(command_str.split(), stdout = PIPE, stderr = PIPE)
        stdout, stderr = process.communicate()
        exit_code = process.wait()
    except Exception as err:
        logging.exception(err)
        print(str(err))
        exit(1)
    finally:
        return exit_code, stdout, stderr

def check_chrome_driver_existence():
    if 'nt' == os.name:
        driver_name = 'chromedriver.exe'
        command_str = 'where ' + driver_name
    else:
        driver_name = 'chromedriver'
        command_str = 'which ' + driver_name
    exit_code, stdout, stderr = run_command(command_str)
    if 0 != exit_code:
        logging.error(stderr)
        error_message = 'Selenium driver (' + driver_name + ') for Chrome browser is not found\n\n' + \
            'If it exists on the system make sure its path is included in PATH ' + \
            'environment variable.\nOtherwise it can be downloaded from the ' + \
            'following page:\nhttps://sites.google.com/a/chromium.org/chromedriver/downloads'
        print(error_message)
        exit(1)
    else:
        command_str = driver_name + ' -v'
        exit_code, stdout, stderr = run_command(command_str)
        logging.info(stdout)

def setup_input_args(script_dir):
    global args, parser
    default_input_file_path = os.path.join(script_dir, 'war_input.ini')

    parser = argparse.ArgumentParser(description='AWS WAR (Well-Architected Review) Tool\n', 
                                     epilog='Script Version ' + script_version + '.', 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-i', '--input', dest='input_file_path', default=default_input_file_path, 
                        help='input file path in \'ini\' format containing questionnaire key/value pairs')
    parser.add_argument('-o', '--output', dest='out_folder_path', 
                        help='folder path to move PDF files into')
    parser.add_argument('-n', '--non-gui', dest='headless', default=False, action='store_true', 
                        help='run Chrome browser in headless (Non-GUI) mode')
    parser.add_argument('-d', '--debug', action='store_true', help='print debug information')
    parser.add_argument('-v', '--version', action='version', 
                        version='Script Version: ' + script_version + '.', 
                        help='print script version information and exit')
    args = parser.parse_args()

def make_directory(dir_path):
    if not os.path.isdir(dir_path):
        if 'nt' == os.name and os.path.isfile(dir_path):
            print('Error: A file with name \'log\' exists.')
            print('Could not create log folder.')
            exit(3)
        try:
            os.mkdir(dir_path)
        except OSError as err:
            print(str(err))
            exit(3)

def get_input_data(input_file_path):
    # Specify default values for some parameters for the case they are missing in the input file.
    # Read, validate and return the input file (ini) content.
    default_values = {'GENERAL': {'signin.url': 'https://console.aws.amazon.com'}}
    if 3 <= get_python_version():
        configs = configparser.ConfigParser(default_values)
        configs.read_dict(default_values)
    else:
        configs = configparser.ConfigParser(default_values)
    try:
        configs.read(input_file_path)
        return configs
    except configparser.Error as err:
        print(str(err))
        logging.exception(err)
        exit(4)

def get_python_version():
    major_version = str(sys.version_info[0])
    minor_version = str(sys.version_info[1])
    python_version = float(major_version + '.' + minor_version)
    return python_version

def request_data(prompt, input_mask = True):
    prompt += ': '
    if input_mask:
        import getpass
        answer = getpass.getpass(prompt)
    else:
        if 3 <= get_python_version():
            answer = input(prompt)
        else:
            answer = str(raw_input(prompt))
    return answer

def open_browser():
    chrome_options = webdriver.ChromeOptions()
    if args.headless:
        chrome_options.add_argument('headless')
    else:
        chrome_options.add_argument('start-maximized')
    try:
        driver = webdriver.Chrome(options = chrome_options)
    except Exception as err:
        logging.exception(err)
        print(str(err))
        exit(3)
    browser_version = driver.capabilities['version']
    logging.info('Chrome Browser Version: ' + browser_version)
    driver_version = driver.capabilities['chrome']['chromedriverVersion'].split()[0]
    logging.info('Chrome Driver Version: ' + driver_version)
    return driver

def open_url(driver, configs):
    signin_url = configs.get('GENERAL', 'signin.url')
    driver.get(signin_url)

def get_element(driver, locator, by_state, max_wait = 20):
    if 'presence' == by_state:
        button = WebDriverWait(driver, max_wait).until(EC.presence_of_element_located(locator))
    elif 'visibility' == by_state:
        button = WebDriverWait(driver, max_wait).until(EC.visibility_of_element_located(locator)) 
    elif 'clickable' == by_state:
        button = WebDriverWait(driver, max_wait).until(EC.element_to_be_clickable(locator))
    return button

def enter_string_with_delay(field, str_to_type):
    logging.disable(logging.DEBUG)
    for char in str_to_type:
        field.send_keys(char)
        time.sleep(random.random())
    logging.disable(logging.NOTSET)

def login(driver, username, password):
    try:
        logging.disable(logging.DEBUG)
        username_field = driver.find_element_by_id('username')
        enter_string_with_delay(username_field, username)
        passwd_field = driver.find_element_by_id('password')
        enter_string_with_delay(passwd_field, password)
        signin_button = driver.find_element_by_id('signin_button')
        signin_button.click()
        while 'Amazon Web Services Sign-In' == driver.title:
            time.sleep(2)
            if args.headless:
                time.sleep(2)
                if 'Amazon Web Services Sign-In' == driver.title:
                    try:
                        mfacode_field = get_element(driver, (By.ID, 'mfacode'), 'visibility')
                        answer = request_data('MFA Code')
                        mfacode_field.send_keys(answer)
                        submitMfa_button = get_element(driver, (By.ID, 'submitMfa_button'), 'visibility')
                        submitMfa_button.click()
                    except TimeoutException as err:
                        logging.exception(err)
                        print(str(err))
                        exit(5) 
        logging.disable(logging.NOTSET)
        logging.info('Logged in')
    except Exception as err:
        logging.exception(err)
        print(str(err))
        exit(5)

def select_region(driver, region):
    nav_regionMenu = get_element(driver, (By.ID, 'nav-regionMenu'), 'presence')
    if region != str(nav_regionMenu.text).strip():
        nav_regionMenu.click()
        region_link = get_element(driver, (By.PARTIAL_LINK_TEXT, region), 'visibility')
        region_link.click()

def open_war_service(driver):
    service_name = 'AWS Well-Architected Tool'
    service_search_field = get_element(driver, (By.ID, 'search-box-input'), 'visibility')
    service_search_field.send_keys(service_name)
    service_search_field.send_keys(Keys.ENTER)

def create_workload(driver, configs):
    create_workload_button = get_element(driver, (By.LINK_TEXT, 'Define workload'), 'visibility')
    create_workload_button.click()
    workload_name = configs.get('WAR', 'name')
    name_field = get_element(driver, (By.XPATH, '//input[@name="name"]'), 'visibility')
    name_field.send_keys(workload_name)
    workload_desc = configs.get('WAR', 'description')
    desc_field = get_element(driver, (By.XPATH, '//textarea[@name="description"]'), 'visibility')
    desc_field.send_keys(workload_desc)
    industry_group = configs.get('WAR', 'industryType').replace(' ', '_')

def run(username, password, configs):
    try:
        driver = open_browser()
        open_url(driver, configs)
        login(driver, username, password)
        select_region(driver, 'N. Virginia')
        open_war_service(driver)
        create_workload(driver, configs)
        # TODO remove the time.sleep call below
        time.sleep(60)
        driver.quit()
    except Exception as err:
        logging.debug(err)
        print(str(err))
        exit(6)

def main():
    script_filename = os.path.basename(sys.argv[0])
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    setup_input_args(script_dir)
    log_dir = os.path.join(script_dir, 'log')
    make_directory(log_dir)
    log_file_path = os.path.join(log_dir, 'debug.log')
    logging_setup(log_file_path)
    check_chrome_driver_existence()
    configs = get_input_data(args.input_file_path)
    username = request_data('Username')
    password = request_data('Password')

    current_datetime = datetime.datetime.now()
    print("Started: " + current_datetime.strftime('%Y-%m-%d %H:%M:%S'))

    run(username, password, configs)

    current_datetime = datetime.datetime.now()
    print("Ended: " + current_datetime.strftime('%Y-%m-%d %H:%M:%S'))
    print("Completed.")

main()