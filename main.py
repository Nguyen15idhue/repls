import os
import random
import logging
import asyncio
import requests


from keep_alive import keep_alive
keep_alive()
from telegram import Update, ForceReply
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          ContextTypes)

# Retrieve bot token from environment variable
my_bot_token = os.environ['TOKEN']
webhook_url = "https://open-sg.larksuite.com/anycross/trigger/callback/OTcyYjYxMTk3ZjIxOTdhYWU3YTMyNzkxNDI0NGVlYzAw"

def load_questions(file_path, level):
    questions = []
    with open(file_path, 'r') as file:
        question_info = []
        for line in file:
            line = line.strip()
            if line:
                question_info.append(line)
                if len(question_info) == 6:
                    question_number, question_content = question_info[0].split(":")
                    choices = [choice[3:] for choice in question_info[1:5]]
                    correct_answer = question_info[5].split(":")[1].strip().lower()
                    questions.append((question_content.strip(),
                                      choices, correct_answer, level))
                    question_info = []
    return questions

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Xin chào {user.mention_html()}, đây là hệ thống tự động kiểm tra trình độ tiếng anh, hãy thực hiện kiểm tra để biết trình độ tiếng anh của bạn!",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Nếu có thắc mắc về đề thi này, vui lòng liên hệ trực tiếp IECenter qua zalo"
    )

async def reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Vui lòng nhập họ và tên của bạn:")
    context.user_data['awaiting_name'] = True
    context.user_data['total_questions_asked'] = 0  # Khởi tạo tổng số câu hỏi đã hỏi

async def handle_name(update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.text.strip()
    context.user_data['name'] = user_name

    await update.message.reply_text(
        f"Chào mừng {user_name}! Vui lòng chọn level từ 1 đến 6:"
    )
    context.user_data['awaiting_level'] = True
    # Khởi tạo số câu đúng cho mỗi level
    context.user_data['correct_count'] = {str(i): 0 for i in range(1, 7)}
    # Khởi tạo danh sách câu hỏi đã được hỏi
    context.user_data['asked_questions'] = []

async def handle_message(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('awaiting_name', False):
        await handle_name(update, context)
        context.user_data['awaiting_name'] = False  # Cập nhật trạng thái sau khi xử lý xong
    elif context.user_data.get('awaiting_level', False):
        await handle_level(update, context)
    elif context.user_data.get('awaiting_answer', False):
        await handle_answer(update, context)
    else:
        await update.message.reply_text(
            "Please start a reading test by using /reading.")

async def handle_level(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> None:
    user_level = update.message.text.strip()
    if user_level.isdigit() and 1 <= int(user_level) <= 6:
        context.user_data['level'] = user_level  # Save selected level
        await update_question_list(context)
        await send_question(update, context)
        context.user_data['awaiting_level'] = False  # Update user state
    else:
        await update.message.reply_text("Vui lòng chỉ chọn level từ 1 đến 6.")

async def update_question_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_level = context.user_data['level']
    file_name = f"lv{user_level}.txt"
    file_path = os.path.join(os.getcwd(), file_name)
    questions = load_questions(file_path, user_level)
    if not questions:
        await update.message.reply_text("Không có câu hỏi nào trong file.")
        return
    lower_level = str(int(user_level) - 1) if user_level != '1' else '1'
    higher_level = str(int(user_level) + 1) if user_level != '6' else '6'
    lower_level_file_path = os.path.join(os.getcwd(), f"lv{lower_level}.txt")
    higher_level_file_path = os.path.join(os.getcwd(), f"lv{higher_level}.txt")
    lower_level_questions = load_questions(lower_level_file_path, lower_level) if os.path.exists(
        lower_level_file_path) else []
    higher_level_questions = load_questions(higher_level_file_path, higher_level) if os.path.exists(
        higher_level_file_path) else []
    mixed_questions = get_mixed_questions(questions, lower_level_questions, higher_level_questions)
    context.user_data['questions'] = mixed_questions
    context.user_data['recent_correct_count'] = 0
    context.user_data['recent_level_correct_count'] = {str(i): 0 for i in range(1, 7)}
    context.user_data['recent_questions_by_level'] = {str(i): 0 for i in range(1, 7)}  
    context.user_data['total_questions_by_level'] = {str(i): 0 for i in range(1, 7)}  # Thêm biến mới

def get_mixed_questions(original_questions, lower_level_questions, higher_level_questions):
    mixed_questions = []
    mixed_questions.extend(original_questions[:10])
    mixed_questions.extend(lower_level_questions[:5])
    mixed_questions.extend(higher_level_questions[:5])
    random.shuffle(mixed_questions)
    return mixed_questions

async def send_question(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('questions'):
        chosen_questions = context.user_data['questions']

        if chosen_questions:
            question_content, choices, correct_answer, level = chosen_questions.pop(0)
            context.user_data['total_questions_asked'] += 1  # Tăng tổng số câu hỏi đã hỏi
            question_number = context.user_data['total_questions_asked']  # Duy trì số thứ tự câu hỏi liên tục
            formatted_question = f"Câu số {question_number} (Level {level}):\n{question_content}\n"
            formatted_choices = "\n".join(
                [f"{chr(ord('a')+i)}. {choice}" for i, choice in enumerate(choices)])

            await asyncio.sleep(0)  # Delay sending the question by 0 second
            await update.message.reply_text(formatted_question + formatted_choices)
            context.user_data['correct_answer'] = correct_answer
            context.user_data['awaiting_answer'] = True
            context.user_data['total_questions_by_level'][str(level)] += 1  # Cập nhật tổng số câu hỏi cho level
            # Thêm câu hỏi đã được hỏi vào danh sách đã hỏi
            context.user_data['asked_questions'].append((question_content, level))
            # Cập nhật số lượng câu hỏi đã được hỏi cho mỗi level
            context.user_data['recent_questions_by_level'][str(level)] += 1
        else:
            await show_result(context, update)
    else:
        await show_result(context, update)

async def handle_answer(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    user_answer = update.message.text.strip().lower()
    if user_answer in ['a', 'b', 'c', 'd']:
        correct_answer = context.user_data.get('correct_answer')
        if user_answer == correct_answer:
            await update.message.reply_text("Chính xác!")
            current_level = context.user_data['asked_questions'][-1][1]
            context.user_data['correct_count'][str(current_level)] += 1
            context.user_data['recent_correct_count'] += 1
            context.user_data['recent_level_correct_count'][str(current_level)] += 1
        else:
            await update.message.reply_text(f"Sai rồi! Đáp án đúng là: {correct_answer}")
        context.user_data['awaiting_answer'] = False

        if len(context.user_data['questions']) == 0:
            result, new_level = await show_result(context, update)
            if new_level is not None:
                context.user_data['level'] = str(new_level)
                await update_question_list(context)
            await send_question(update, context)
        else:
            await send_question(update, context)
    else:
        await update.message.reply_text("Vui lòng chỉ chọn đáp án từ A đến D.")
        return

async def show_result(context, update):
    correct_count = context.user_data.get('correct_count', {})
    recent_correct_count = context.user_data.get('recent_correct_count', 0)
    recent_level_correct_count = context.user_data.get('recent_level_correct_count', {})
    total_questions_asked = context.user_data.get('total_questions_asked', 0)
    recent_questions_by_level = context.user_data.get('recent_questions_by_level', {})
    total_questions_by_level = context.user_data.get('total_questions_by_level', {})
    total_correct_count = sum(correct_count.values())  # Tính tổng số câu đúng

    result_message = "Kết quả của bạn:\n"
    result_message += "-" * 70 + "\n"
    for level in range(1, 7):
        level_correct = correct_count.get(str(level), 0)
        recent_level_correct = recent_level_correct_count.get(str(level), 0)
        recent_level_questions = recent_questions_by_level.get(str(level), 0)
        total_level_questions = total_questions_by_level.get(str(level), 0)  # Lấy tổng số câu hỏi cho level
        percent_correct_in_recent = 0 if recent_level_questions == 0 else round(recent_level_correct / recent_level_questions * 100, 2)
        result_message += f"Level {level}: {level_correct} câu đúng,trong đó {recent_level_correct} câu đúng trong 20 câu gần nhất\n"
        result_message += f"Phần trăm đúng của level {level} trong 20 câu gần nhất: {recent_level_correct}/{recent_level_questions}, {percent_correct_in_recent}%\n"
        result_message += "---\n"
    result_message += f"\n---->Số câu đúng đã trả lời là {total_correct_count}\n"  # Hiển thị tổng số câu đúng
    result_message += f"---->Số câu đã hỏi là {total_questions_asked}\n"  # Hiển thị số câu đã hỏi
    result_message += "-" * 70

    await update.message.reply_text(result_message)

    # Kiểm tra và đồng bộ thông tin qua webhook khi số câu hỏi đạt 20
    if total_questions_asked >= 20 and context.user_data.get('sync_data', True):
        user_name = context.user_data['name']
        level_correct = {level: correct_count[str(level)] for level in range(1, 7)}
        total_questions_asked = context.user_data.get('total_questions_asked', 0)
        total_correct_count = sum(correct_count.values())
        sync_data = {
            'user_name': user_name,
            'correct_count': correct_count,
            'level_correct': level_correct,
            'total_questions_asked': total_questions_asked,
            'total_correct_count': total_correct_count
        }
        try:
            requests.post(webhook_url, json=sync_data)
        except Exception as e:
            logging.error(f"Failed to sync user data via webhook: {e}")
        context.user_data['sync_data'] = False

    current_level = int(context.user_data['level'])
    lower_level_percent = recent_level_correct_count.get(str(current_level - 1), 0) / recent_questions_by_level.get(str(current_level - 1), 1) * 100 if current_level > 1 else 0
    higher_level_percent = recent_level_correct_count.get(str(current_level + 1), 0) / recent_questions_by_level.get(str(current_level + 1), 1) * 100 if current_level < 6 else 0

    if current_level == 1:
        if lower_level_percent < 50:
            new_level = 1
            await update.message.reply_text("Bạn đang ở level 1, không thể giảm level nữa nên sẽ tiếp tục kiểm tra tại level 1.")
        elif higher_level_percent >= 80 and lower_level_percent > 50:
            new_level = current_level + 1
            await update.message.reply_text(f"Bạn đang ở level {current_level}, level mới của bạn là level {new_level}")
        else:
            new_level = current_level
            await update.message.reply_text(f"Bạn đang ở level {current_level}, level mới của bạn là level {new_level}")

    elif current_level == 6:
        if higher_level_percent >= 80 and lower_level_percent > 50:
            new_level = 6
            await update.message.reply_text("Bạn đang ở level 6, không thể tăng level nữa nên sẽ tiếp tục kiểm tra tại level 6.")
        elif lower_level_percent < 50:
            new_level = current_level - 1
            await update.message.reply_text(f"Bạn đang ở level {current_level}, level mới của bạn là level {new_level}")
        else:
            new_level = current_level
            await update.message.reply_text(f"Bạn đang ở level {current_level}, level mới của bạn là level {new_level}")
    else:
        if lower_level_percent < 50:
            new_level = current_level - 1
            await update.message.reply_text(f"Bạn đã bị giảm xuống level {new_level}.")
        elif higher_level_percent >= 80:
            new_level = current_level + 1
            await update.message.reply_text(f"Bạn đã được cập nhật lên level {new_level}.")
        else:
            new_level = current_level
            await update.message.reply_text(f"Bạn đang ở level {current_level}, level mới của bạn là level {new_level}")

    if new_level != current_level:
        context.user_data['level'] = str(new_level)
        await update_question_list(context)

    return result_message, new_level

async def answer(update: Update,
                 context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'questions' not in context.user_data:
        await update.message.reply_text("Không có dữ liệu câu hỏi.")
        return

    correct_count = context.user_data.get('correct_count', {})
    recent_correct_count = context.user_data.get('recent_correct_count', 0)
    recent_level_correct_count = context.user_data.get('recent_level_correct_count', {})
    total_questions_asked = context.user_data.get('total_questions_asked', 0)
    recent_questions_by_level = context.user_data.get('recent_questions_by_level', {})
    total_questions_by_level = context.user_data.get('total_questions_by_level', {})
    total_correct_count = sum(correct_count.values())  # Tính tổng số câu đúng
  
    result_message = "Kết quả của bạn:\n"
    result_message += "-" * 70 + "\n"
    for level in range(1, 7):
        level_correct = correct_count.get(str(level), 0)
        recent_level_correct = recent_level_correct_count.get(str(level), 0)
        recent_level_questions = recent_questions_by_level.get(str(level), 0)
        total_level_questions = total_questions_by_level.get(str(level), 0)  # Lấy tổng số câu hỏi cho level
        percent_correct_in_recent = 0 if recent_level_questions == 0 else round(recent_level_correct / recent_level_questions * 100, 2)
        result_message += f"Level {level}: {level_correct} câu đúng trong {total_level_questions} câu, {recent_level_correct} câu đúng trong 20 câu gần nhất\n"
        result_message += f"Phần trăm đúng của level {level} trong 20 câu gần nhất: {recent_level_correct}/{recent_level_questions}, {percent_correct_in_recent}%\n"
        result_message += "---\n"
    result_message += f"\n---->Số câu đúng đã trả lời là {total_correct_count}\n"  # Hiển thị tổng số câu đúng
    result_message += f"---->Số câu đã hỏi là {total_questions_asked}\n"  # Hiển thị số câu đã hỏi
    result_message += "-" * 70

    await update.message.reply_text(result_message)


async def check_and_stop(context):
    total_questions_asked = context.user_data.get('total_questions_asked', 0)
    if total_questions_asked == 200:
        await context.bot.send_message(chat_id=context.effective_chat.id, text="Đã đạt đến 200 câu hỏi. Bạn đã hoàn thành kiểm tra.")
        application = context.application
        await application.stop()

def main():
    application = Application.builder().token(my_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reading", reading))
    application.add_handler(CommandHandler("answer", answer))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()