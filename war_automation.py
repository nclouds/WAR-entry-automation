#!/usr/bin/env python

""" 
    Selenium Automation Script for entering information into AWS WAR (Well-Architected Review) Portal
    
    Defaults:
        Input configuration file path: <script_dir>/war_input.ini
        Output directory path: <script_dir>/<customer_name_dir>/

    Exit codes and their descriptions:
        0 - Normal termination
        1 - Selenium is not installed
        2 - Selenium driver for Chrome browser is not installed
        3 - Error occurred during the initial setup
        4 - Invalid content in the input ini file
        5 - Login failed
        6 - Error during automation

    Script Version: 1.0.
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
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ModuleNotFoundError:
    print('Selenium is not installed.\n\nFor installation run the following command: ' + \
          'pip install selenium\nFor more details visit: https://pypi.org/project/selenium/')
    exit(1)
except Exception as err:
    print(str(err))
    exit(1)

script_version = "1.0" 
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
    global args

    default_input_file_path = os.path.join(script_dir, 'war_input.ini')
    parser = argparse.ArgumentParser(description='AWS WAR (Well-Architected Review) Tool\n\n' + \
                                     'Script Version ' + script_version + '\n', 
                                     epilog='Default Input File: ' + default_input_file_path + '\n' + \
                                            'Default Output Directory: ' + script_dir + os.sep + '<customer_name_dir>', 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-i', '--input', dest='input_file_path', default=default_input_file_path, 
                        help='input file (\'ini\' format) path containing parameters and the answers index/value pairs')
    parser.add_argument('-o', '--output', dest='output_dir', help='directory path to move PDF file into and save ARN file')
    parser.add_argument('-n', '--non-gui', dest='headless', default=False, action='store_true', 
                        help='run Chrome browser in headless (Non-GUI) mode')
    parser.add_argument('-d', '--debug', action='store_true', help='print debug/info messages and create debug log')
    parser.add_argument('-s', '--slow', dest='run_slowly', action='store_true', 
                        help='run the script with up to 1 second random delays between some calls')
    parser.add_argument('-v', '--version', action='version', 
                        version='Script Version: ' + script_version + '.', 
                        help='print script version information and exit')
    args = parser.parse_args()

def make_directory(dir_path):
    if not os.path.isdir(dir_path):
        if 'nt' == os.name and os.path.isfile(dir_path):
            print('Error: A file with name \'log\' exists.')
            print('Could not create log directory.')
            exit(3)
        try:
            os.makedirs(dir_path)
        except OSError as err:
            if args.debug:
                logging.exception(err)
            print(str(err))
            exit(3)

def get_input_data(input_file_path, script_dir):
    # Specify default value for outDir parameter for the case it is missing in the input file.
    # Get configurations from the input file (ini).
    try:
        configs = configparser.ConfigParser()
        configs.add_section('DEFAULTS')
        configs.set('DEFAULTS', 'outDir', script_dir)
        configs.read(input_file_path)
        mandatory_sections = ['GENERAL', 'WAR']
        for section in mandatory_sections:
            if not configs.has_section(section):
                print('Section \'' + section + '\' is missing in the input file')
                exit(4)
        if '' == configs.get('GENERAL', 'signin.url'):
            print('Missing value for "signin.url" parameter in the configuration file')
            exit(4)
        war_mandatory_keys = ['name', 'description', 'industryType', 'industry', 'environment', 
                              'regions', 'accountIDs', 'milestone']
        for key in war_mandatory_keys:
            if not configs.has_option('WAR', key):
                print('Parameter \'' + key + '\' is missing in the input file')
                exit(4)
            elif '' == configs.get('WAR', key) and 'accountIDs' != key:
                print('Missing value for "' + key +'" parameter in the configuration file')
                exit(4)
        has_question_section = False
        sections = configs.sections()
        for section in sections:
            if section.startswith('QUESTION'):
                has_question_section = True
        if not has_question_section:
            print('No section with \'QUESTION\' prefix in the input file')
            exit(4)
        return configs
    except configparser.Error as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(4)

def request_data(prompt, input_mask = True, mandatory = True):
    prompt += ': '
    if input_mask:
        answer = getpass.getpass(prompt)
    else:
        if 3 <= get_python_version():
            answer = input(prompt)
        else:
            answer = str(raw_input(prompt))
    if 0 == len(answer.strip()) and mandatory:
        print(prompt[:-2] + ' is not specified, exiting.')
        exit(0)
    return answer

def open_browser():
    chrome_options = webdriver.ChromeOptions()
    if args.headless:
        chrome_options.add_argument('headless')
    chrome_options.add_argument('start-maximized')
    try:
        driver = webdriver.Chrome(options = chrome_options)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(3)
    if args.debug:
        browser_version = driver.capabilities['version']
        info_str = 'Chrome Browser Version: ' + browser_version
        print(info_str)
        logging.info(info_str)
    if args.debug:
        driver_version = driver.capabilities['chrome']['chromedriverVersion'].split()[0]
        info_str = 'Chrome Driver Version: ' + driver_version
        print(info_str)
        logging.info(info_str)
    return driver

def open_url(driver, configs):
    try:
        signin_url = configs.get('GENERAL', 'signin.url')
        if args.debug or args.headless:
            print('Opening URL: \'' + signin_url + '\'')
        driver.get(signin_url)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(6)

def get_element(driver, locator, by_state, max_wait = 20):
    try:
        if 'presence' == by_state:
            element = WebDriverWait(driver, max_wait).until(EC.presence_of_element_located(locator))
        elif 'visibility' == by_state:
            element = WebDriverWait(driver, max_wait).until(EC.visibility_of_element_located(locator)) 
        elif 'clickable' == by_state:
            element = WebDriverWait(driver, max_wait).until(EC.element_to_be_clickable(locator))
        elif 'invisibility' == by_state:
            element = WebDriverWait(driver, max_wait).until(EC.invisibility_of_element_located(locator))
    except Exception as err:
        print('The element \'' + locator[1] + '\' is not found or it is in inaccessible state.\n')
        if args.debug:
            logging.exception(err)
            print('Check log for more info.')
        exit(6)
    return element

def get_elements(driver, locator, by_state, max_wait = 20):
    try:
        if 'presence' == by_state:
            elements = WebDriverWait(driver, max_wait).until(
                                     EC.presence_of_all_elements_located(locator))
        elif 'visibility' == by_state:
            elements = WebDriverWait(driver, max_wait).until(
                                     EC.visibility_of_all_elements_located(locator))
    except Exception as err:
        print('The elements \'' + locator[1] + '\' are not found or they are in inaccessible state.\n')
        if args.debug:
            logging.exception(err)
            print('Check log for more info.')
        exit(6)
    return elements

def enter_string(field, str_to_type, delay = False):
    if args.debug:
        logging.disable(logging.DEBUG)
    if delay:
        for char in str_to_type:
            field.send_keys(char)
            time.sleep(random.random())
    else:
        field.send_keys(str_to_type)
    if args.debug:
        logging.disable(logging.NOTSET)

def login(driver, username, password):
    try:
        delay = False
        if args.run_slowly:
            delay = True
        if args.debug:
            logging.disable(logging.DEBUG)
        username_field = driver.find_element_by_id('username')
        enter_string(username_field, username, delay)
        passwd_field = driver.find_element_by_id('password')
        enter_string(passwd_field, password, delay)
        signin_button = driver.find_element_by_id('signin_button')
        signin_button.click()
        while 'Amazon Web Services Sign-In' == driver.title:
            time.sleep(2)
            if args.headless:
                time.sleep(2)
                if 'Amazon Web Services Sign-In' == driver.title:
                    try:
                        # Notify and exit when the entered username and/or password is not correct 
                        element = driver.find_element_by_class_name('mainError')
                        print(str(element.text))
                        request_data('Press Enter key to exit', input_mask = False, mandatory = False)
                        driver.quit()
                        exit(6)
                    except NoSuchElementException:
                        pass
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
        info_str = 'Logged in'
        if args.debug:
            logging.disable(logging.NOTSET)
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
            logout(driver)
            exit(4)
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
                    logout(driver)
                    print('The script exited')
                    exit(4)
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
        while question_text == str(WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, 
                                                                   'awsui-util-action-stripe-title'))).text):
            time.sleep(1.5)
            max_wait -= 1.5
            if 0 >= max_wait:
                print('The page loading did not finish in more than 1 minute.')
                logout(driver)
                exit(6)
    except TimeoutException as err:
        if args.debug:
            logging.exception(err)
        print('The question text at the top of the page was not found.')
        logout(driver)
        exit(6)

def save_milestone_and_pdf(driver, configs):
    milestone_name = configs.get('WAR', 'milestone')
    save_milestone_button = get_element(driver, (By.ID, 'viewWorkload-recordMilestone'), 'clickable')
    save_milestone_button.click()
    # Wait until 'Save milestone' modal dialog appears
    get_element(driver, (By.CLASS_NAME, 'awsui-modal-container'), 'visibility')
    milestone_name_inputbox = get_element(driver, (By.XPATH, '//input[@name="milestoneName"]'), 'clickable')
    milestone_name_inputbox.send_keys(milestone_name)
    save_button = get_element(driver, (By.ID, 'viewWorkloadRecordMilestoneRecordButton'), 'clickable')
    save_button.click()
    # Wait until 'Save milestone' modal dialog disappears
    get_element(driver, (By.CLASS_NAME, 'awsui-modal-container'), 'invisibility')
    generate_pdf_button = get_element(driver, (By.ID, 'viewWorkload_generatePDFButton'), 'clickable')
    generate_pdf_button.click()
    # Wait until PDF file download finishes
    generate_pdf_button = get_element(driver, (By.XPATH, '//*[@id="viewWorkload_generatePDFButton"]//button[@type="submit"]'),
                                     'presence')
    while not generate_pdf_button.is_enabled():
        time.sleep(1)

def move_PDF_file(driver, configs, output_dir):
    import shutil
    if 'nt' == os.name:
        downloads_dir = os.path.join(os.environ['USERPROFILE'], 'Downloads')
    else:
        downloads_dir = os.path.join(os.environ['HOME'], 'Downloads')
    workload_name = configs.get('WAR', 'name')
    pdf_file_path = os.path.join(downloads_dir, workload_name + '.pdf')
    max_wait = 15
    while not os.path.isfile(pdf_file_path):
        time.sleep(1)
        max_wait -= 1
        if 0 >= max_wait:
            print('File "' + pdf_file_path + '" is not found')
            logout(driver)
            exit(6)
    time.sleep(2)
    try:
        shutil.move(pdf_file_path, output_dir)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print('Failed to move "' + pdf_file_path + '" file into "' + output_dir + '" directory')
        return
    print('File "' + pdf_file_path + '" is moved into "' + output_dir + '" directory')

def is_last_question(driver):
    try:
        driver.find_element_by_xpath('//*[@id="questionWizard-saveAndExitButton-finalQuestion" and @class=""]')
        return True
    except NoSuchElementException:
        return False

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
        question_text = str(WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CLASS_NAME, 
                                                            'awsui-util-action-stripe-title'))).text)
        if args.debug or args.headless:
            logging.info('Section Name: ' + section)
            logging.info('Question: ' + question_text)
            print('\tSection Name: ' + section)
            print('Question: ' + question_text)
        keys = configs.options(section) 
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

        # Answer notes field
        if 0 < len(notes):
            notes_textarea = get_element(driver, (By.CSS_SELECTOR, 'textarea[id^="awsui-textarea"][name="answerNotes"]'), 
                                         'clickable')
            notes_textarea.send_keys(notes)
        if not does_not_apply:
            # Questions section automation
            question_checkboxes = get_elements(driver, (By.CSS_SELECTOR, 'input[id^="awsui-checkbox"]'), 'presence')
            for key in keys:
                if not key.isdigit():
                    if args.debug:
                        logging.error('Expected: number (answer index), Got: ' + key)
                    print('Invalid answer numbering in the input file \'' + section + '\' section')
                    print('Expected: number\nGot: ' + key)
                    logout(driver)
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
                            answer = request_data('Do you want to continue and ignore all such mismatches? (y/n)', 
                                                  input_mask = False)
                            if answer.lower().startswith('y'):
                                ignore_answers_count_mismatch = True
                                break
                            else:
                                logout(driver)
                                print('The script exited')
                                exit(4)
        # Check if it is the last question and perform corresponding action
        is_last = is_last_question(driver)
        if is_last and (section != sections[-1]):
            print('The specified questions count in the configuration file exceeds the actual one')
            request_data('Press Enter key to exit', input_mask = False, mandatory = False)
            logout(driver)
            exit(6)
        elif not is_last and (section == sections[-1]):
            print('The specified questions count in the configuration file is less than the actual one')
            request_data('Press Enter key to exit', input_mask = False, mandatory = False)
            logout(driver)
            exit(6)
        else:
            if not is_last:
                next_button = get_element(driver, (By.ID, 'questionWizard-nextQuestionButton'), 'clickable')
                next_button.click()
                check_loading_state(driver, question_text)
        if args.run_slowly:
            # Add some randomness
            time.sleep(random.random())
    save_and_exit_button = get_element(driver, (By.ID, 'questionWizard-saveAndExitButton-finalQuestion'), 'clickable')
    save_and_exit_button.click()
    save_milestone_and_pdf(driver, configs)

def create_file(file_path, data, mode = 'w'):
    try:
        with open(file_path, mode) as f:
            f.write(data)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print('Failed to create file:\n' + file_path)

def save_ARN(driver, configs, output_dir):
    milestones_link = get_element(driver, (By.LINK_TEXT, 'Milestones'), 'clickable')
    milestones_link.click()
    milestone_name = configs.get('WAR', 'milestone')
    milestone_link = get_element(driver, (By.LINK_TEXT, milestone_name), 'clickable')
    milestone_link.click()
    properties_link = get_element(driver, (By.LINK_TEXT, 'Properties'), 'clickable')
    properties_link.click()
    ARN = str(get_element(driver, (By.ID, 'viewWorkload_workloadArn_milestone'), 'visibility').text)
    workload_name = configs.get('WAR', 'name')
    ARN_file_path = os.path.join(output_dir, 'ARN-' + workload_name + '.txt')
    create_file(ARN_file_path, ARN)
    print('ARN is saved: "' + ARN_file_path + '"')

def logout(driver):
    print('Logging out')
    username_menu = get_element(driver, (By.ID, 'nav-usernameMenu'), 'clickable')
    username_menu.click()
    logout_button = get_element(driver, (By.ID, 'aws-console-logout'), 'clickable')
    logout_button.click()
    print('Closing the browser')
    driver.quit()

def run(username, password, configs, output_dir):
    try:
        driver = open_browser()
        open_url(driver, configs)
        login(driver, username, password)
        select_region(driver, 'N. Virginia')
        open_war_service(driver)
        create_workload(driver, configs)
        review(driver, configs)
        move_PDF_file(driver, configs, output_dir)
        save_ARN(driver, configs, output_dir)
        logout(driver)
    except Exception as err:
        if args.debug:
            logging.exception(err)
        print(str(err))
        exit(6)

def setup_output_destination(configs, customer_name):
    output_dir = configs.get('GENERAL', 'outDir')
    if '' == output_dir:
        output_dir = configs.get('DEFAULTS', 'outDir')
    if args.output_dir is not None:
        output_dir = args.output_dir
    if not os.path.isabs(output_dir):
        output_dir = os.path.abspath(output_dir) 
    workload_name = configs.get('WAR', 'name')
    customer_dir = os.path.join(output_dir, customer_name) 
    pdf_file_path = os.path.join(customer_dir, workload_name + '.pdf')
    if os.path.isfile(pdf_file_path):
        print('File "' + pdf_file_path + '" exists.')
        answer = request_data('Do you want to overwrite? (y/n)', input_mask = False)
        if answer.lower().startswith('y'):
            try:
                os.remove(pdf_file_path)
            except OSError as err:
                if args.debug:
                    logging.exception(err)
                print("Failed to remove the file:\n" + str(err))
                print('The script exited')
                exit(3)
        else:
            print('The script exited')
            exit(0)
    make_directory(customer_dir)
    return customer_dir

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
        input_file_path = os.path.abspath(args.input_file_path)
        if not os.path.isfile(input_file_path):
            print('Input file is missing: ' + input_file_path)
            exit(3)
        configs = get_input_data(input_file_path, script_dir)
        customer_name = request_data('Custmer Name', input_mask = False)
        output_dir = setup_output_destination(configs, customer_name)
        username = request_data('Username')
        password = request_data('Password')
        datetime_format = '%Y-%m-%d %H:%M:%S'
        current_datetime = datetime.datetime.now()
        print("Started: " + current_datetime.strftime(datetime_format))
        run(username, password, configs, output_dir)
        current_datetime = datetime.datetime.now()
        print("Ended: " + current_datetime.strftime(datetime_format))
    except KeyboardInterrupt as err:
        print('\nScript execution interrupted by the user')
        if args.debug:
            logging.exception(err)
    except Exception as err:
        print('\n' + str(err))
        if args.debug:
            logging.exception(err)

main()