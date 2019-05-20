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
import getpass
from subprocess import Popen, PIPE
try:
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver import ActionChains
    from selenium.common.exceptions import TimeoutException
except ModuleNotFoundError:
    print('Selenium is not installed.\n\nFor installation run the following command: ' + \
          'pip install selenium\nFor more details visit: https://pypi.org/project/selenium/')
    exit(1)
except Exception as err:
    print(str(err))
    exit(1)

# TODO Add version number
script_version = "N/A (Under development)" 
args = None

def get_python_version():
    major_version = str(sys.version_info[0])
    minor_version = str(sys.version_info[1])
    python_version = float(major_version + '.' + minor_version)
    return python_version

if 3 <= get_python_version():
    import configparser
else:
    import ConfigParser as configparser

def logging_setup(log_file_path):
    logging.basicConfig(filename = log_file_path, format = '%(asctime)s %(message)s', 
                        level=logging.DEBUG)

def run_command(command_str):
    try:
        process = Popen(command_str.split(), stdout = PIPE, stderr = PIPE)
        stdout, stderr = process.communicate()
        exit_code = process.wait()
        if args.debug:
            logging.info(stdout)
            print(stdout.decode())
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
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
        if args.debug:
            logging.error(stderr)
        error_message = 'Selenium driver (' + driver_name + ') for Chrome browser is not found\n\n' + \
            'If it exists on the system make sure its path is included in PATH ' + \
            'environment variable.\nOtherwise it can be downloaded from the ' + \
            'following page:\nhttps://sites.google.com/a/chromium.org/chromedriver/downloads'
        print(error_message)
        exit(2)

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
    parser.add_argument('-d', '--debug', action='store_true', help='print debug information and create log')
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
            if args.debug:
                logging.exception(err)
            print(str(err))
            exit(3)

def get_input_data(input_file_path):
    # Specify default values for some parameters for the case they are missing in the input file.
    # Read, validate and return the input file (ini) content.
    default_values = {'signin.url': 'https://console.aws.amazon.com'}
    try:
        if 3 <= get_python_version():
            configs = configparser.ConfigParser()
            configs.read(input_file_path)
            configs['DEFAULT'] = default_values
        else:
            configs = configparser.ConfigParser(default_values)
            configs.read(input_file_path)
        war_mandatory_keys = ['name', 'description', 'industryType', 'industry', 'environment', 
                              'regions', 'accountIDs']
        for key in war_mandatory_keys:
            if not configs.has_option('WAR', key):
                print('Key \'' + key + '\' is missing in the input file.')
                exit(4)
        return configs
    except configparser.Error as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(4)

def request_data(prompt, input_mask = True):
    prompt += ': '
    if input_mask:
        answer = getpass.getpass(prompt)
    else:
        if 3 <= get_python_version():
            answer = input(prompt)
        else:
            answer = str(raw_input(prompt))
    if 0 == len(answer.strip()):
        print(prompt[:-2] + ' is not specified, exiting.')
        exit(0)
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
        print(str(err))
        if args.debug:
            logging.exception(err)
        exit(3)
    browser_version = driver.capabilities['version']
    if args.debug:
        info_str = 'Chrome Browser Version: ' + browser_version
        print(info_str)
        logging.info(info_str)
    driver_version = driver.capabilities['chrome']['chromedriverVersion'].split()[0]
    if args.debug:
        info_str = 'Chrome Driver Version: ' + driver_version
        print(info_str)
        logging.info(info_str)
    return driver

def open_url(driver, configs):
    try:
        signin_url = configs.get('GENERAL', 'signin.url')
        # TODO implement signin from the default login page
        if '' == signin_url:
            signin_url = configs.get(configs.default_section, 'signin.url')
        if args.debug:
            print('Open URL: \'' + signin_url + '\'')
        driver.get(signin_url)
    except Exception as err:
        print(str(err))
        exit(6)

def get_element(driver, locator, by_state, max_wait = 20):
    try:
        if 'presence' == by_state:
            button = WebDriverWait(driver, max_wait).until(EC.presence_of_element_located(locator))
        elif 'visibility' == by_state:
            button = WebDriverWait(driver, max_wait).until(EC.visibility_of_element_located(locator)) 
        elif 'clickable' == by_state:
            button = WebDriverWait(driver, max_wait).until(EC.element_to_be_clickable(locator))
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print('The element \'' + locator[1] + '\' is not found or it is in inaccessible state.\n' + \
              'Check log for more info.')
        exit(6)
    return button

def get_elements(driver, locator, by_state, max_wait = 20):
    elements = WebDriverWait(driver, max_wait).until(
                             EC.presence_of_all_elements_located(locator))
    return elements
    #visibility_of_all_elements_located

def enter_string_with_delay(field, str_to_type):
    if args.debug:
        logging.disable(logging.DEBUG)
    for char in str_to_type:
        field.send_keys(char)
        time.sleep(random.random())
    if args.debug:
        logging.disable(logging.NOTSET)

def login(driver, username, password):
    try:
        if args.debug:
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
                        submitMfa_button = get_element(driver, (By.ID, 'submitMfa_button'), 'clickable')
                        submitMfa_button.click()
                    except TimeoutException as err:
                        if args.debug:
                            logging.exception(err)
                        print(str(err))
                        exit(5) 
        if args.debug:
            logging.disable(logging.NOTSET)
            info_str = 'Logged in'
            logging.info(info_str)
            print(info_str)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(5)

def select_region(driver, region):
    nav_regionMenu = get_element(driver, (By.ID, 'nav-regionMenu'), 'clickable')
    if region != str(nav_regionMenu.text).strip():
        nav_regionMenu.click()
        region_link = get_element(driver, (By.PARTIAL_LINK_TEXT, region), 'clickable')
        region_link.click()

def open_war_service(driver):
    service_name = 'AWS Well-Architected Tool'
    service_search_field = get_element(driver, (By.ID, 'search-box-input'), 'clickable')
    service_search_field.send_keys(service_name)
    service_search_field.send_keys(Keys.ENTER)

def create_workload(driver, configs):
    #  Define workload - Workload properties input
    define_workload_button = get_element(driver, (By.LINK_TEXT, 'Define workload'), 'clickable')
    define_workload_button.click()
    workload_name = configs.get('WAR', 'name')
    name_field = get_element(driver, (By.XPATH, '//input[@name="name"]'), 'clickable')
    name_field.send_keys(workload_name)
    workload_desc = configs.get('WAR', 'description')
    desc_field = get_element(driver, (By.XPATH, '//textarea[@name="description"]'), 'clickable')
    desc_field.send_keys(workload_desc)

    industry_type_combobox = get_element(driver, (By.NAME, 'industryGroup'), 'clickable')
    industry_type_combobox.click()
    industry_type = configs.get('WAR', 'industryType')
    # Change the value to match item id naming convention
    industry_type = industry_type.replace('& ', '')
    industry_type = industry_type.replace(' ', '_')
    industry_type_item = get_element(driver, (By.XPATH, '//li[contains(@id, "' + industry_type + '")]'), 'clickable')
    industry_type_item.click()

    industry_name_combobox = get_element(driver, (By.ID, 'subIndustrySelect'), 'clickable')
    industry_name_combobox.click()
    industry_name = configs.get('WAR', 'industry')
    # Change the value to match item id naming convention
    industry_name = industry_type.replace('& ', '')
    industry_name = industry_type.replace(' ', '_')
    industry_name_item = get_element(driver, (By.XPATH, '//li[contains(@id, "' + industry_name + '")]'), 'clickable')
    industry_name_item.click()

    environment = configs.get('WAR', 'environment').lower()
    if environment.startswith('prod'):
        radio_button_value = 'prod'
    elif environment.startswith('pre-prod'):
        radio_button_value = 'preprod'
    else:
        print('Invalid value is specified for environment: ' + environment + \
              '\nValid options are: Production, Pre-production')
        environment = request_data('Environment', input_mask = False)
        if environment.startswith('prod'):
            radio_button_value = 'prod'
        elif environment.startswith('pre-prod'):
            radio_button_value = 'preprod'
        else:
            print('Invalid input')
            driver.quit()
            exit(6)
    environment_radio_button = get_element(driver, (By.XPATH, '//input[@type="radio" and @value="' + \
                                                    radio_button_value + '"]'), 'presence')
    actions = ActionChains(driver)
    actions.move_to_element(environment_radio_button)
    actions.click(environment_radio_button)
    actions.perform()

    aws_regions_checkbox = get_element(driver, (By.XPATH, '//*[@id="workloadRegionsCheckbox"]//input[@type="checkbox"]'), 
                                                'presence')
    aws_regions_checkbox.click()
    regions = configs.get('WAR', 'regions').lower().split(',')
    for region in regions:
        aws_regions_combobox = get_element(driver, (By.ID, 'awsui-multiselect-0'), 'clickable')
        aws_regions_combobox.click()
        regions_item = get_element(driver, (By.XPATH, '//li[contains(@id, "' + region + '")]'), 'clickable')
        regions_item.click()
    skip_ids = False
    account_ids = configs.get('WAR', 'accountIDs')
    if '' != account_ids:
        for account_id in account_ids.split(','):
            account_id = account_id.strip()
            if 12 != len(account_id) or not account_id.isdigit():
                print('Invalid Account ID in the input file: ' + account_id)
                answer = request_data('Do you want to continue without entering Account IDs? (y/n)', input_mask = False)
                if not answer.lower().startswith('y'):
                    print('The script exited')
                    exit(6)
                else:
                    skip_ids = True
                    break
    else:
        skip_ids = True
    if not skip_ids:
        account_ids_textarea = get_element(driver, (By.ID, 'awsui-textarea-2'), 'clickable')
        account_ids_textarea.send_keys(account_ids)
    define_workload_button = get_element(driver, (By.ID, 'defineWorkload-createWorkloadButton'), 'clickable')
    define_workload_button.click()

def check_loading_state(driver, question_text):
    # Wait until the next question will be loaded
    try:
        max_wait = 60
        while question_text == str(WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, 'awsui-util-action-stripe-title'))).text):
            time.sleep(1.5)
            max_wait -= 1.5
            if 0 >= max_wait:
                print('The page loading did not finish in more than 1 minute.')
                exit(6)
    except TimeoutException as err:
        if args.debug:
            logging.exception(err)
        print('The question text at the top of the page was not found.')
        exit(6)

def save_milestone_and_pdf(driver, configs):
    milestone_name = configs.get('WAR', 'milestone')
    save_milestone_button = get_element(driver, (By.ID, 'viewWorkload-recordMilestone'), 'clickable')
    save_milestone_button.click()
    milestone_name_inputbox = get_element(driver, (By.NAME, 'milestoneName'), 'clickable')
    milestone_name_inputbox.send_keys()
    save_button = get_element(driver, (By.ID, 'viewWorkloadRecordMilestoneRecordButton'), 'clickable')
    save_button.click()
    generate_pdf_button = get_element(driver, (By.ID, 'viewWorkload_generatePDFButton'), 'clickable')
    generate_pdf_button.click()

def review(driver, configs):
    ignore_answers_count_mismatch = False
    start_review_button = get_element(driver, (By.LINK_TEXT, 'Start review'), 'clickable')
    start_review_button.click()
    sections = configs.sections()
    sections_count = len(sections)
    
    for section in sections:
        if not section.startswith('QUESTION'):
            continue
        # Get the question text to compare later for loading state checking
        question_text = str(WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CLASS_NAME, 'awsui-util-action-stripe-title'))).text)
        if args.debug:
            logging.info(question_text)
            print(question_text)
        keys = configs.options(section) 
        # Removing default parameter 'signin.url'
        try:
            keys.remove('signin.url') 
        except: 
            pass
        does_not_apply = False
        notes = ''
        if configs.has_option(section, 'doNotApply'):
            does_not_apply = configs.getboolean(section, 'doNotApply')
            keys.remove('donotapply')
        if configs.has_option(section, 'notes'):
            notes = configs.get(section, 'notes')
            keys.remove('notes')

        # 'Question does not apply to this workload' toggle button
        toggle_button = get_element(driver, (By.CSS_SELECTOR, '*[id^="awsui-toggle"]'), 
                                    'clickable')
        is_checked = False
        if str(toggle_button.get_attribute('class')).endswith('checked'):
            is_checked = True      
        if does_not_apply != is_checked:
            toggle_button.click()

        # Notes
        if 0 < len(notes):
            notes_textarea = get_element(driver, (By.CSS_SELECTOR, 'textarea[id^="awsui-textarea"][name="answerNotes"]'), 
                                         'clickable')
            notes_textarea.send_keys(notes)
        if not does_not_apply:
            # Questions section automation
            question_checkboxes = get_elements(driver, (By.CSS_SELECTOR, 
                                                        'input[id^="awsui-checkbox"]'), 'clickable')
            for key in keys:
                if not key.isdigit():
                    if args.debug:
                        logging.error('Expected: \'question.NUMBER.NUMBER\'\nGot: ' + key)
                    print('Invalid answer numbering in the input file \'' + section + '\' section')
                    print('Expected: number\nGot: ' + key)
                    exit(4)
                if configs.getboolean(section, key):
                    try:
                        checkbox = question_checkboxes[int(key) - 1]
                        checkbox.click()
                    except IndexError as err:
                        if args.debug:
                            logging.exception(err)
                        if not ignore_answers_count_mismatch:
                            print('Answers count mismatch for question \'' + section + '\'')
                            print('Expected (in input file): ' + str(len(keys)))
                            print('Actual: ' + str(len(question_checkboxes)))
                            answer = request_data('Do you want to continue and ignore all such mismatches? (y/n)', input_mask = False)
                            if answer.lower().startswith('y'):
                                ignore_answers_count_mismatch = True
                                break
                            else:
                                print('The script exited')
                                exit(4)
        # If not the last question
        if sections.index(section) + 1 < sections_count:
            next_button = get_element(driver, (By.ID, 'questionWizard-nextQuestionButton'), 'clickable')
            next_button.click()
            check_loading_state(driver, question_text)
        # Add some randomness
        time.sleep(random.random())
    save_and_exit_button = get_element(driver, (By.ID, 'questionWizard-saveAndExitButton-finalQuestion'), 'clickable')
    save_and_exit_button.click()
    # TODO implemented partly
    #save_milestone_and_pdf(driver, configs)
    time.sleep(60)

def run(username, password, configs):
    try:
        driver = open_browser()
        open_url(driver, configs)
        login(driver, username, password)
        select_region(driver, 'N. Virginia')
        open_war_service(driver)
        create_workload(driver, configs)
        review(driver, configs)
        # TODO remove time.sleep call below
        time.sleep(60)
        driver.quit()
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(6)

def main():
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        setup_input_args(script_dir)
        if args.debug:
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
    except KeyboardInterrupt as err:
        print('\nScript execution canceled by the user')
        if args.debug:
            logging.exception(err)
    except Exception as err:
        print('\n' + str(err))
        if args.debug:
            logging.exception(err)

main()