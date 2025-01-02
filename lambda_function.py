#import logging

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import boto3
import logging
from datetime import datetime
#logger = telebot.logger
#telebot.logger.setLevel(logging.INFO)

API_TOKEN = os.environ['TOKEN']
TABLE_ITEMS = os.environ['TABLE_ITEMS']
TABLE_TIME = os.environ['TABLE_TIME']
TABLE_TIME_CONSUMPTION = os.environ['TABLE_TIME_CONSUMPTION']
allowed_chat_id = set(os.environ['ALLOWED_CHATID'].split(',')) # string of all allowed chat id separated by ",", e.g. 12345,67890,24681
ADMIN_CHATID = os.environ['CHATID']
msg_start = "Here are the available commands:\n\n/help\n/morehelp\n/list: list all items\n/get xxx: get qnty of item\n/add xxx: add 1 unit of item\n/bulkadd xxx y: bulk add y units of item\n/consume xxx: consume 1 unit of item\n/delete xxx: delete item from list\n\n(Replace xxx with item name. Alternatively, leave blank to get a dropdown menu of existing items, with exception of bulk commands.)"
msg_start2 = "Additional commands:\n\n/remove xxx: remove 1 unit of item without logging consumption time (accidental adds)\n/bulkconsume xxx y: bulk consume y units of item\n/bulkremove xxx y: bulk remove y units of item (no consumption logging)"
bot = telebot.TeleBot(API_TOKEN, threaded=False)

def lambda_handler(event, context):
    try:
        process_event(event) # Process event from aws and respond
    except Exception as e:
        print('<Error> ' + str(e))
        logging.exception('<Error> ' + str(e))
        return {'statusCode': 200}
    return {'statusCode': 200 } # return after logging error to prevent lambda handler from looping

def process_event(event):
    request_body_dict = json.loads(event['body']) # Get telegram webhook json from event
    update = telebot.types.Update.de_json(request_body_dict) # Parse updates from json
    if update.message is not None:  # normal message
        chat_id = update.message.chat.id
        user = update.message.from_user.username
    else: # callback query, might not be necessary
        chat_id = update.callback_query.message.chat.id
        user = update.callback_query.message.from_user.username

    try:
        if str(chat_id) in allowed_chat_id:
            bot.process_new_updates([update]) # Run handlers and etc for updates
        else:
            print(update)
            bot.send_message(chat_id,'Invalid User ' + str(chat_id)) # notify user
            bot.send_message(ADMIN_CHATID,'Invalid bot user, chat ID:' + str(chat_id) + ', username: ' + user) # notify admin
    except Exception as e:
        bot.send_message(chat_id,'<Error> ' + str(e))
        raise e

# Handle '/start' and '/help'
@bot.message_handler(commands=['help', 'start'])
def help(msg):
    chat_id = msg.chat.id
    bot.send_message(chat_id,msg_start)

@bot.message_handler(commands=['morehelp'])
def morehelp(msg):
    chat_id = msg.chat.id
    bot.send_message(chat_id,msg_start2)

# Handle '/list'
@bot.message_handler(commands=['list'])
def list_items(msg):
    msg_output = ""
    chat_id = str(msg.chat.id)
    scanned_items = getAllItems(chat_id)
    for item in scanned_items:
        msg_output += "\n"
        msg_output += (item["product"]['S'] + " " + item["qnty"]['N'])
    bot.send_message(chat_id, msg_output)
    
# Handle '/get'
@bot.message_handler(commands=['get'])
def get_item(msg):
    chat_id = str(msg.chat.id)
    item_name = msg.text[5:].strip()
    
    if item_name == '': # item name not specified
        scanned_items = getAllItems(chat_id)                    
        bot.send_message(chat_id, 'Get what?', reply_markup = generate_keyboard(scanned_items))
    else:                
        getItem(chat_id, item_name)

# Handle '/add'
@bot.message_handler(commands=['add'])
def add_item(msg):
    chat_id = str(msg.chat.id)
    item_name = msg.text[5:].strip()
    
    if item_name == '': # item name not specified
        scanned_items = getAllItems(chat_id)
        bot.send_message(chat_id, 'Add what?', reply_markup = generate_keyboard(scanned_items))
    else:
        updateItem(chat_id, item_name, str(1))

@bot.message_handler(commands=['bulkadd'])
def bulk_add_item(msg):
    chat_id = str(msg.chat.id)
    item_ls = msg.text[9:].strip().split(' ')
    if len(item_ls) != 2:
        raise Exception('Invalid format for bulk add')
    else:
        item_name, qnty = item_ls
        try: int(qnty)
        except Exception as e:
            raise Exception('Invalid quantity')
    updateItem(chat_id, item_name, qnty)

# Handle '/remove and /consume'
@bot.message_handler(commands=['remove','consume'])
def remove_item(msg):
    chat_id = str(msg.chat.id)
    if msg.text[:7] == '/remove':
        item_name = msg.text[8:].strip()
        consume = False
    else: # consume
        item_name = msg.text[9:].strip()
        consume = True

    if item_name == '': # item name not specified
        scanned_items = getAllItems(chat_id)
        scanned_items = [item for item in scanned_items if int(item["qnty"]['N']) > 0]# only list items with 1 or more units
        if consume:
            bot.send_message(chat_id, 'Consume what?', reply_markup = generate_keyboard(scanned_items))
        else:
            bot.send_message(chat_id, 'Remove what?', reply_markup = generate_keyboard(scanned_items))
        # response to be handled in handleCallbackQuery function
    else:
        reduceItem(chat_id, item_name, 1, consume) # check current qty before updating

# Handle '/bulkremove and /bulkconsume'
@bot.message_handler(commands=['bulkremove','bulkconsume'])
def bulk_remove_item(msg):
    chat_id = str(msg.chat.id)
    if msg.text[:11] == '/bulkremove':
        item_ls = msg.text[12:].strip().split(' ')
        consume = False
    else: # consume
        item_ls = msg.text[13:].strip().split(' ')
        consume = True
    
    if len(item_ls) != 2:
        raise Exception('Invalid format for bulk remove/consume')
    else:
        item_name, qnty = item_ls
        try: int(qnty)
        except Exception as e:
            raise Exception('Invalid quantity')

    reduceItem(chat_id, item_name, int(qnty), consume) # check current qty before updating

# Handle '/delete'
@bot.message_handler(commands=['delete'])
def delete_item(msg):
    chat_id = str(msg.chat.id)
    item_name = msg.text[8:].strip()

    if item_name == '': # item name not specified
        scanned_items = getAllItems(chat_id)
        bot.send_message(chat_id, 'Delete what?', reply_markup = generate_keyboard(scanned_items))
    else:
        deleteItem(chat_id, item_name)

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    handleCallbackQuery(call)
    
# Helper functions
def handleCallbackQuery(call):
    chat_id = str(call.message.chat.id)
    message_id = call.message.message_id
    item_name = call.data
    question = call.message.text
    bot.edit_message_reply_markup(chat_id, message_id = message_id) # to remove inline keyboard
    
    if item_name == '(Cancel)':
        bot.send_message(chat_id, 'Operation cancelled.')
    else:
        if question == 'Add what?':
            updateItem(chat_id, item_name, str(1))
        elif question == 'Remove what?':
            updateItem(chat_id, item_name, str(-1))
        elif question == 'Consume what?':
            updateItem(chat_id, item_name, str(-1), consume = True)
        elif question == 'Delete what?':
            deleteItem(chat_id, item_name)
        elif question == 'Get what?':
            getItem(chat_id, item_name)
    return

def reduceItem(chat_id, item_name, qnty, consume): # qnty is positive int
    item_qnty = getItemQnty(chat_id, item_name)
    if item_qnty is None:
        bot.send_message(chat_id, 'Error, ' + item_name + ' not found!')
    elif int(item_qnty) - qnty < 0:
        bot.send_message(chat_id, 'Error, ' + item_name + ' has insufficient units!')
    else: 
        updateItem(chat_id, item_name, str(-qnty), consume)
    return
    
def deleteItem(chat_id, item_name):
    dynamo = boto3.client('dynamodb')
    item_qnty = getItemQnty(chat_id, item_name)
    key = {"chatId": {'S': chat_id}, 'product': {'S': item_name}}
    dynamo.delete_item(TableName=TABLE_ITEMS, Key=key)
    if item_qnty is None:
        bot.send_message(chat_id, 'Error, ' + item_name + ' not found!')
    else:
        bot.send_message(chat_id, 'Deleted ' + item_name + '. Previously ' + item_qnty + ' units remaining.')
    return
    
def getItemQnty(chat_id, item_name):
    dynamo = boto3.client('dynamodb')
    key = {"chatId": {'S': chat_id}, 'product': {'S': item_name}}
    item = dynamo.get_item(TableName=TABLE_ITEMS, Key=key)
    if 'Item' in item: # item found (can be 0 units)
        item = item['Item']
        item_qnty = item["qnty"]['N']
    else: # item not found
        item_qnty = None
    return item_qnty
    
def getItem(chat_id, item_name):
    item_qnty = getItemQnty(chat_id, item_name)
    if item_qnty is None:
        bot.send_message(chat_id, 'Item ' + item_name + ' not found!')
    else:
        bot.send_message(chat_id, 'There are ' + item_qnty + ' units of ' + item_name)
    return 

def getAllItems(chat_id):
    dynamo = boto3.client('dynamodb')
    scanned_items = dynamo.scan(TableName=TABLE_ITEMS, FilterExpression = "chatId = :chatId", ExpressionAttributeValues = {":chatId" : {"S" : chat_id}})["Items"] 
    return scanned_items

def updateItem(chat_id, item_name, value, consume = False):
    dynamo = boto3.client('dynamodb')
    key = {"chatId": {'S': chat_id}, "product":{'S': item_name}}
    updateTime = str(round((datetime.now() - datetime(1970,1,1)).total_seconds())) # time in +8 GMT #-timedelta(hours = 8)
    dynamo.update_item(Key=key, TableName=TABLE_ITEMS, UpdateExpression = "add qnty :val", ExpressionAttributeValues = {":val": {"N": value}})
    
    item_qnty = getItemQnty(chat_id, item_name)
    if int(value) < 0: # remove or consume item
        if consume:
            key2 = {"chatId_product": {'S': chat_id + '_' + item_name}, "consumed_at":{'N': updateTime}, 'qnty':{"N": value}}
            dynamo.put_item(Item=key2, TableName=TABLE_TIME_CONSUMPTION)
        # datetime.fromtimestamp(1734974370)
        bot.send_message(chat_id, 'Removed ' + str(abs(int(value))) + ' units of ' + item_name + ', ' + item_qnty + ' units remaining.')
    else: # adding item
        key2 = {"chatId_product": {'S': chat_id + '_' + item_name}, "added_at":{'N': updateTime}, 'qnty':{"N": value}}
        dynamo.put_item(Item=key2, TableName=TABLE_TIME)
        bot.send_message(chat_id, 'Added ' + value + ' units of ' + item_name + ', ' + item_qnty + ' units now.')
    return

def generate_keyboard(items):
    markup = InlineKeyboardMarkup()
    params = [InlineKeyboardButton(item["product"]['S'], callback_data = item["product"]['S']) for item in items]
    markup.add(*params)
    markup.row(InlineKeyboardButton('(Cancel)', callback_data = '(Cancel)'))
    return markup