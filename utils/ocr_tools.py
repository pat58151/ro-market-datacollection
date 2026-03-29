import re
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor

def extract_and_average_numbers(raw_text):
    """
    Applies character substitutions and extracts relevant numbers (>=100) from text.
    Returns the list of numbers and the text after substitution.
    """

    replacements = {'O': '0', 'o': '0', 'C': '0', 'c': '0', 'l': '1', 'I': '1', 'B': '8', 'S': '5', 's': '5', 'Z': '',
                    'z': ''}
    for old, new in replacements.items():
        raw_text = raw_text.replace(old, new)

    nums = [
        int(n.replace(',', ''))
        for n in re.findall(r'\d[\d,]*\d|\d', raw_text)
        if int(n.replace(',', '')) >= 100
    ]

    return nums, raw_text


def fix_ocr_errors(numbers):
    """
    Applies contextual fixes for common OCR errors:
    1. Removes trailing '2' often mistaken for currency/suffix.
    2. Fixes missing digits in the last number based on context.
    """
    if len(numbers) < 1:
        return []
    cleaned = []
    for num in numbers:
        s = str(num)
        cleaned.append(int(s[:-1]) if s.endswith('2') and len(s) > 1 else num)

    if len(cleaned) < 2:
        return cleaned

    last = cleaned[-1]
    last_str = str(last)

    # Find the most common digit length among previous numbers
    digits = [len(str(n)) for n in cleaned[:-1]]
    if not digits:
        return cleaned

    target_len = max(set(digits), key=digits.count)

    # If last number is shorter than expected
    if len(last_str) < target_len:
        firsts = [str(n)[0] for n in cleaned[:-1]]
        most_common_first = max(set(firsts), key=firsts.count)

        missing_digits = target_len - len(last_str)

        # Missing trailing digits case
        if last_str[0] == most_common_first:
            last = int(last_str + '0' * missing_digits)
        # Missing leading digits case
        else:
            prev_number_str = str(cleaned[-2])
            digits_needed = missing_digits - 1
            digits_to_copy = prev_number_str[1:1 + digits_needed]
            while len(digits_to_copy) < digits_needed:
                digits_to_copy += '0'
            last = int(most_common_first + digits_to_copy + last_str)

        cleaned[-1] = last

    return cleaned


async def read_price_from_image(ocr_reader, processed_img):
    """
    Performs EasyOCR on the prepared image, cleans the results, and returns the
    average price from the extracted numbers.

    Runs OCR in a thread pool to avoid blocking the event loop.

    Returns:
        tuple: (average_price: int, fixed_numbers: list) on success
               (None, []) on failure
    """
    if ocr_reader is None:
        print("OCR reader is None")
        return None, []

    try:
        img_np = np.array(processed_img)

        # Run OCR in thread pool to avoid blocking the asyncio event loop
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,  # Uses default ThreadPoolExecutor
            lambda: ocr_reader.readtext(img_np, detail=0, allowlist='0123456789.,')
        )

        if not results:
            print("OCR returned no results")
            return None, []

        raw_text = " ".join(results)
        numbers, _ = extract_and_average_numbers(raw_text)
        fixed_numbers = fix_ocr_errors(numbers)

        if fixed_numbers:
            average_price = round(sum(fixed_numbers) / len(fixed_numbers))
            print(f"OCR success: Found {len(fixed_numbers)} prices, average: {average_price}")
            return average_price, fixed_numbers
        else:
            print("No valid numbers found after OCR processing")
            return None, []

    except Exception as e:
        print(f"Error during EasyOCR processing in read_price_from_image: {e}")
        import traceback
        traceback.print_exc()
        return None, []