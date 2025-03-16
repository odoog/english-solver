import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher

# Function to load the configuration
def load_config():
    with open('config.json', 'r', encoding='utf-8') as config_file:
        return json.load(config_file)

# Function to find the best matching question
def count_strings_in_text(strings, text):
    count = 0
    for string in strings:
        print(f"Ищем строку {string} в тексте")
        count += len(re.findall(re.escape(string), text))
    return count

def get_right_answers(question_text, answer_container_text, answers):
    best_match = []
    highest_ratio = 0

    for stored_question in answers.keys():
        ratio = SequenceMatcher(None, question_text, stored_question).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = answers[stored_question]
        elif ratio == highest_ratio:
            best_match.extend(answers[stored_question])

    if len(best_match) == 1:
        return best_match[0]
    else:
        max_answer_similarity = -1
        print(best_match)
        for best_match_option in best_match:
            answer_similarity_for_match = count_strings_in_text(best_match_option, answer_container_text)
            if answer_similarity_for_match > max_answer_similarity:
                print(f"Обновляем max_answer_similarity - [{max_answer_similarity}], ответ [{best_match_option}]")
                max_answer_similarity = answer_similarity_for_match
                best_match_by_answer_similarity = best_match_option
        print(f"Лучший ответ-метч к вопросу {answer_container_text} это {best_match_by_answer_similarity}")
        return best_match_by_answer_similarity

def get_correct_answers_for_type(plain_right_answer_text):
    correct_answers = []

    # Check if the correct answers are in an ordered list format
    if "Для этих элементов правильный порядок выглядит так:" in plain_right_answer_text:
        soup = BeautifulSoup(plain_right_answer_text, 'html.parser')
        ol_tag = soup.find('ol', class_='correctorder')
        
        if ol_tag:
            correct_answers = [li.get_text(strip=True) for li in ol_tag.find_all('li')]

    else:
        # Parse correct answers from brackets []
        correct_answers = re.findall(r'\[(.*?)\]', plain_right_answer_text)

        # If no brackets are found, use the plain text answer
        if not correct_answers:
            plain_text_answer = re.sub(r'<.*?>', '', plain_right_answer_text).replace("Правильный ответ:", "").strip()
            if plain_text_answer:
                correct_answers.append(plain_text_answer)
    
    correct_answers = [answer.strip() for answer in correct_answers]
    return correct_answers

def get_answers_from_url(url, driver):
    # Fetch the HTML content from the URL

    driver.get(url)

    answers_page_text = driver.page_source

    soup = BeautifulSoup(answers_page_text, 'html.parser')
    
    answers = {}
    feedback_elements = soup.select(".feedback")

    for feedback in feedback_elements:
        # Extract the correct answer
        right_answer_element = feedback.select_one(".rightanswer")
        right_answer_text = right_answer_element.decode_contents()

        # Extract question text
        question_element = feedback.find_previous("div", class_="formulation")
        question_text = question_element.select_one(".qtext").get_text(strip=True)

        correct_answers = get_correct_answers_for_type(right_answer_text)

        if not question_text in answers: 
            answers[question_text] = []

        answers[question_text].append(correct_answers)

    # Save answers to right_answers.json
    with open("right_answers.json", "w", encoding="utf-8") as json_file:
        json.dump(answers, json_file, ensure_ascii=False, indent=4)

    return answers

def get_radio_button_value(value):
    if value == "Верно":
        return "1"
    else:
        return "0"

def answer_question(answers):
    question_text = driver.find_element(By.CSS_SELECTOR, ".qtext").text
    # Find the div/span with class "answer"
    answer_container = driver.find_element(By.CSS_SELECTOR, ".content")

    right_answers = get_right_answers(question_text, answer_container.text, answers)

    if right_answers:
        print(f"Found best match right answer for question: \n{question_text} \nAnswer: {right_answers}")
    else:
        print(f"No answer found for: {question_text}")
        return

    # Handle dropdown selects within the answer container
    select_elements = answer_container.find_elements(By.TAG_NAME, "select")
    for idx, select_element in enumerate(select_elements):
        options = select_element.find_elements(By.TAG_NAME, "option")
        for option in options:
            if option.text == right_answers[idx]:
                option.click()
                break

    # Handle text inputs within the answer container
    input_elements = answer_container.find_elements(By.CSS_SELECTOR, "input[type='text']")
    for idx, input_element in enumerate(input_elements):
        if idx < len(right_answers):
            input_element.clear()
            input_element.send_keys(right_answers[idx])

    # Handle radio buttons within the answer container
    radio_buttons = answer_container.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    if len(right_answers) == 1:
        for radio in radio_buttons:
            radio_button_value = radio.get_attribute("value")
            right_answer_value = get_radio_button_value(right_answers[0])
            if radio_button_value == right_answer_value:
                radio.click()
                break

    # Handle sortable list if present
    sortable_list = answer_container.find_elements(By.CSS_SELECTOR, "ul.sortablelist")
    if sortable_list:
        # Now reorder the list items to match the correct_answers
        for correct_answer in right_answers:
            list_items = sortable_list[0].find_elements(By.CSS_SELECTOR, "li.sortableitem")
            item_text_map = {item.text.strip(): item for item in list_items}
            
            if correct_answer in item_text_map:
                print(f"Moving element: {correct_answer} to top")
                list_item = item_text_map[correct_answer]
                driver.execute_script("arguments[0].parentNode.appendChild(arguments[0]);", list_item)
                print(f"Передвинули элемент {list_item}")
            else:
                print(f"No list item found for: {correct_answer} in list")
        time.sleep(config['sleep_after_sortable_list'])

if __name__ == "__main__":
    config = load_config()

    # Set up Selenium WebDriver
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    # Login
    driver.get("https://online.mospolytech.ru/login/index.php")
    username_field = driver.find_element(By.ID, "username")
    password_field = driver.find_element(By.ID, "password")
    login_button = driver.find_element(By.ID, "loginbtn")

    username_field.send_keys(config["username"])
    password_field.send_keys(config["password"])
    login_button.click()

    # Get answers from URL
    answers = get_answers_from_url(config['quiz_review_url'], driver)

    # Navigate to the quiz URL
    driver.get(config['quiz_url'])

    # Loop through questions
    while True:
        try:
            answer_question(answers)
        except Exception as e:
            print(f"An error occurred: {e}. Skip this question.")

        time.sleep(config['sleep_between_questions'])
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "input[value='Следующая страница']")
            next_button.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".qtext")))
        except:
            break

    print("Ответы завершены, ожидание перед завершением.")
    
    # Wait for user to press Enter to finish the script
    input("Press Enter to finish...")

    driver.quit()
