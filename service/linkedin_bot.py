import logging
import os
import sys
import threading
import traceback
from multiprocessing import Queue
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import MaxRetryError

logging.basicConfig(level=logging.INFO, filename='chat_bot.log', format='%(process)d - %(asctime)s - %(levelname)s - '
                                                                        '%(message)s', datefmt='%d-%b-%y %H:%M:%S')


def get_driver():
    path_to_chrome_driver = os.path.join(os.getcwd(), 'chromedriver')
    print(path_to_chrome_driver)
    # driver = webdriver.Chrome(executable_path=path_to_chrome_driver)
    # driver.maximize_window()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("--disable-dev-shm-usage") # для докера
    chrome_prefs = {}  # для докера
    chrome_options.experimental_options["prefs"] = chrome_prefs # для докера
    chrome_prefs["profile.default_content_settings"] = {"images": 2} # для докера
    chrome_options.add_argument("--window-size=1440x900")
    chrome_options.add_argument('start-maximized')
    chrome_options.add_argument('disable-infobars')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36")
    driver = webdriver.Chrome(executable_path=path_to_chrome_driver, options=chrome_options)
    return driver


class MainSelenium:
    URL = None

    def __init__(self, chat_id, ):
        self.chat_id = chat_id
        self.queue_output = Queue()
        self.queue_input = Queue()
        self.queue_kmd_output = Queue()
        self.queue_kmd_input = Queue()

    def _wait_elems(self, xpath, timeout=5):
        return WebDriverWait(self.driver, timeout).until(EC.presence_of_all_elements_located((By.XPATH, xpath)))

    def interaction_with(self, xpath, timeout=10, clickable=False, scroll=False, click=False, text=None):
        """ Функция взаимодействия с элементомами. Возвращает запрошенный элемент """
        # Дожидаемся появления элемента на странице
        elems = self._wait_elems(xpath, timeout)

        # Проверяем сколько элементов обнаружено
        if len(elems) > 1:
            # Если найдена группа элементов, то возвращаем список элементов
            return elems
        else:
            # Иначе - начинаем взаимодействие
            elem = elems[0]

        if clickable:
            # Дожидаемся кликабельности элемента
            WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath)))

        if scroll:
            # Скроллим элемент в пределы видимости:
            elem.location_once_scrolled_into_view

        if click:
            # Нажимаем на элемент
            elem.click()
        if text is not None:
            # Вводим текст
            elem.send_keys(text)

        return elem

    def invisibility(self, xpath, timeout):
        """Функция ожидания исчезновения загрузочного элемента"""
        WebDriverWait(self.driver, timeout).until_not(EC.presence_of_element_located((By.XPATH, xpath)))


class Linkedin(MainSelenium):
    URL = "https://www.linkedin.com/home"
    EMAIL = None
    PASSWORD = None
    VERIFY = None
    INDEX_COMPANY = None
    WAIT_FOR = None

    def q_kmd_input_waiter(self):
        while True:
            if not self.queue_kmd_input.empty():
                message = self.queue_kmd_input.get()
                if message == "_kmd_chat_bot_exit":
                    self.exit()
                else:
                    pass
            sleep(0.1)

    def registration(self):
        """Функция регистрации аккаунта"""

        # Заходим на сайт
        self.driver.get(self.URL)
        logging.info("Зашли на сайт")

        # Находим по xpath  кнопку "Войти", нажимаем
        self.interaction_with('//a[@class="nav__button-secondary"]', clickable=True, click=True)

        self.queue_output.put('Введите E-Mail:')
        logging.info('Введите E-Mail:')

        self.EMAIL = self.queue_input.get()

        logging.info("Вводим email...")

        # Находим по xpath поле "Адрес эл. почты или телефон", вводим email
        self.interaction_with('//input[@id="username"]', text=self.EMAIL)

        self.queue_output.put('Введите пароль:')
        logging.info('Введите пароль:')

        self.PASSWORD = self.queue_input.get()

        logging.info("Вводим пароль...")

        # Находим по xpath поле "Пароль", вводим пароль
        self.interaction_with('//input[@id="password"]', text=self.PASSWORD)

        self.queue_output.put("Проверка введенных данных...")
        logging.info("Проверка введенных данных...")

        # Находим по xpath кнопку "Войти", нажимаем
        self.interaction_with('//button[@type="submit"]', clickable=True, click=True)

        try:
            self.interaction_with('//input[@id="input__email_verification_pin"]')

            self.queue_output.put('Попытка входа кажется сайту подозрительной. Введите пароль, который был отправлен '
                                  'вам на указанный email:')

            logging.info('Попытка входа кажется сайту подозрительной. Введите пароль, который был отправлен вам на '
                         'указанный email:')

            self.VERIFY = self.queue_input.get()

            self.interaction_with('//input[@id="input__email_verification_pin"]', text=self.VERIFY)
            self.interaction_with('//button[@id="email-pin-submit-button"]', clickable=True, click=True)

            take_screenshot(self.driver)

            logging.info("Ввели пароль верификации")
        except:
            logging.info("Пароль верификации не потребовался")
            pass

        # Находим по xpath кнопку "Профиль", нажимаем
        try:
            self.interaction_with('//button[@type="button"]//img', clickable=True, click=True)
            logging.info("Все ок, зашли в профиль")
        except TimeoutException:
            take_screenshot(self.driver)
            logging.warning("Что-то пошло не так...Возможно, вы ввели неверные данные")
            self.queue_output.put("Что-то пошло не так...Возможно, вы ввели неверные данные.")
            self.exit()

        # Находим по xpath кнопку "См. профиль", нажимаем
        self.interaction_with('//a[text()="См. профиль"]', clickable=True, click=True)

        self.queue_output.put("Поиск предыдущих мест работы...")

        logging.info("Поиск предыдущих мест работы...")

        # Скроллим вниз страницы
        self.interaction_with('//span[text()="Контактная информация"]', timeout=10, scroll=True)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def find_last_companies(self):
        """Функция поиска предыдущих мест работы"""
        last_companies = []
        try:
            companies = self.interaction_with('//span[text()="Название компании"]//following-sibling::span')
            if isinstance(companies, WebElement):
                c = companies.text
                last_companies.append(c)
            else:
                for c in companies:
                    c = c.text
                    last_companies.append(c)
            for comp in companies:
                last_companies.append(comp)
        except:
            pass
        all_text = []
        try:
            all_elems = self.interaction_with('//span[@class="pv-entity__secondary-title separator"]/parent::p')
        except:
            self.queue_output.put("Предыдущие места работы не найдены")
            logging.info("Предыдущие места работы не найдены")

            self.exit()

        if isinstance(all_elems, WebElement):
            text = all_elems.text
            all_text.append(text)
        else:
            for elem in all_elems:
                text = elem.text
                all_text.append(text)

        child_text = []
        child_elems = self.interaction_with('//span[@class="pv-entity__secondary-title separator"]')
        if isinstance(child_elems, WebElement):
            text = child_elems.text
            child_text.append(text)
        else:
            for elem in child_elems:
                text = elem.text
                child_text.append(text)

        for text, ch_text in zip(all_text, child_text):
            parent_text = text.replace(ch_text, '')
            last_companies.append(parent_text)

        logging.info("Найден список предыдущих компаний")

        return last_companies

    def input_required_companies(self, last_companies):
        """Функция выбора из списка требуемых компаний для просмотра предыдущих сотрудников"""
        for index, company in enumerate(last_companies):
            punkt = str(index + 1) + ".  " + company
            self.queue_output.put(punkt)
            logging.info(punkt)
        required_companies = []
        while True:
            try:
                self.queue_output.put('Введите через запятую номера компаний из списка для поиска предыдущих сотрудников:')
                logging.info('Введите через запятую номера компаний из списка для поиска предыдущих сотрудников:')

                self.INDEX_COMPANY = self.queue_input.get().split(",")

                for i in self.INDEX_COMPANY:
                    required_companies.append(last_companies[int(i) - 1].strip())
                break
            except (ValueError, IndexError):
                self.INDEX_COMPANY = None
                self.queue_output.put("Введенные значения не являются номерами компаний из списка")
                logging.info("Введенные значения не являются номерами компаний из списка")
                continue

        logging.info("Получен список требуемых компаний для поиска")

        return required_companies

    def find_variants_companies(self, required_company):
        """Функция отбора предложенных сайтом вариантов прежней компании в фильтрах"""
        # Находим по xpath поле "Поиск", вводим название компании
        logging.info("Находим  по xpath поле 'Поиск', вводим название компании")
        self.interaction_with('//div[@aria-label="Поиск"]/input', clickable=True, text=Keys.CONTROL + "A")
        self.interaction_with('//div[@aria-label="Поиск"]/input', clickable=True, text=Keys.BACK_SPACE)
        self.interaction_with('//div[@aria-label="Поиск"]/input', clickable=True, text=required_company)

        # Находим по xpath кнопку "См. все результаты", нажимаем
        logging.info('Находим по xpath кнопку "См. все результаты", нажимаем')
        self.interaction_with('//span[@class="search-global-typeahead__hit-text t-16 t-black"]', clickable=True,
                              click=True)

        # Находим по xpath кнопку "Люди", нажимаем
        logging.info('Находим по xpath кнопку "Люди", нажимаем')
        self.interaction_with('//button[text()="Люди"]', clickable=True, click=True)

        # Находим по xpath кнопку "Все фильтры", нажимаем
        logging.info('Находим по xpath кнопку "Все фильтры", нажимаем')
        self.interaction_with('//button[text()="Все фильтры"]', clickable=True, click=True)

        variants_companies = [c for c in self.interaction_with('//h3[text()="Прежняя компания"]/parent::li//p')]

        logging.info("Отобран список предложенных сайтом вариантов прежней компании в фильтрах""")

        return variants_companies

    def checking_company(self, variants_companies, required_company):
        """Функция выбора в фильтрах требуемой компании из предложенного сайтом списка"""
        for v_comp in variants_companies:
            if v_comp.text == required_company:
                sleep(2)
                v_comp.click()

        # Находим по xpath кнопку "Показать результаты", нажимаем
        logging.info('Находим по xpath кнопку "Показать результаты", нажимаем')
        self.interaction_with('(//span[@class="artdeco-button__text" and text()="Показать результаты"])[1]', timeout=10,
                              scroll=True, clickable=True, click=True)
        logging.info("Выбрана требуемая компания фильтрах из предложенного сайтом списка")

    def find_last_employees_names(self):
        """Функция выбора на странице имен предыдущих сотрудников компании"""
        names_list = self.interaction_with('//span[@dir="ltr"]/span[1]')
        last_employees_names = []

        if isinstance(names_list, WebElement):
            last_employees_names.append(names_list.text)
        else:
            for name in names_list:
                last_employees_names.append(name.text)

        logging.info("Выбраны имена предыдущих сотрудников компании на странице")

        return last_employees_names

    def go_to_next_page(self, required_company):
        """Функция перехода на следующую страницу"""
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        try:
            cur_cirle = self.interaction_with('(//li[contains(@class, "selected")])/button[contains(@aria-label, "Page")]')
            logging.info('Пробуем нажать кнопку "Далее" на странице')
            self.interaction_with('//button[@aria-label="Далее"]', scroll=True, clickable=True, click=True)
            WebDriverWait(self.driver, 5).until(EC.staleness_of(cur_cirle))
            next_page = True
            logging.info("Перешли на следующую страницу")
        except TimeoutException:
            self.queue_output.put("Все предыдущие сотрудники компании " + required_company + " загружены")
            logging.info("Все предыдущие сотрудники компании " + required_company + " загружены")
            next_page = False
        return next_page

    def find_hrefs(self):
        """Функция поиска ссылок на профили бывших сортрудников выбранной компании"""
        elems = self.interaction_with('//div/a[@class="my_flask_app-aware-link"]')
        list_of_hrefs = []
        if isinstance(elems, WebElement):
            elems = [elems]
        for elem in elems:
            href = elem.get_attribute("href")
            list_of_hrefs.append(href)

        logging.info("Найден список ссылок на профили бывших сортрудников выбранной компании")

        return list_of_hrefs

    def names_and_profiles(self, last_employees_names, list_of_hrefs):
        """Функция вывода имени и ссылки на профиль каждого бывшего сотрудника выбранной компании"""
        names_and_profiles = list(zip(last_employees_names, list_of_hrefs))

        for name in names_and_profiles:
            self.queue_output.put(" : ".join(name))

        logging.info("Выведен список имя+ссылка на профиль каждого бывшего сотрудника выбранной компании")

        return names_and_profiles

    def processing(self, required_companies):
        """Функция обработки каждой компании из выбранных пользователем"""
        for required_company in required_companies:
            self.queue_output.put("Предыдущие сотрудники компании " + required_company + ":")
            logging.info("Предыдущие сотрудники компании " + required_company + ":")
            variants_companies = self.find_variants_companies(required_company)
            self.checking_company(variants_companies, required_company)
            num = 1
            while True:
                try:
                    self.queue_output.put('Страница ' + str(num) + ":")
                    logging.info('Страница ' + str(num) + ":")
                    last_employees_names = self.find_last_employees_names()
                    list_of_hrefs = self.find_hrefs()
                    self.names_and_profiles(last_employees_names, list_of_hrefs)
                    next_page = self.go_to_next_page(required_company)
                    if next_page:
                        num += 1
                        continue
                    else:
                        num = 1
                        break
                except TimeoutException:
                    self.queue_output.put("Доступные для контакта профили на данной странице не найдены")
                    logging.info("Доступные для контакта профили на данной странице не найдены")
                    next_page = self.go_to_next_page(required_company)
                    if next_page:
                        num += 1
                        continue
                    else:
                        num = 1
                        break

    def exit(self):
        self.driver.quit()
        self.queue_kmd_output.put("_kmd_chat_bot_exit_is_ok")
        logging.info("Exit")
        sys.exit()


def take_screenshot(driver):
    name = 'screenshot_{}.png'
    c = 1
    while os.path.exists(name.format(c)):
        c += 1
    driver.save_screenshot(name.format(c))
    logging.info("Был сделан скриншот " + name.format(c))


def main(linkedin):
    try:
        linkedin.driver = get_driver()
        threading.Thread(target=linkedin.q_kmd_input_waiter).start()
        linkedin.registration()
        last_companies = linkedin.find_last_companies()
        required_companies = linkedin.input_required_companies(last_companies)
        linkedin.processing(required_companies)
        linkedin.exit()
    except MaxRetryError:
        logging.warning("Выходим из сайта...")
    except Exception:
        take_screenshot(linkedin.driver)
        logging.warning("Вышли из поиска с ошибкой")
        logging.error(traceback.format_exc())
        linkedin.exit()
        sleep(500)


if __name__ == '__main__':
    main()
