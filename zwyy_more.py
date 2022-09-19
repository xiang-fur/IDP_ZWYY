#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

import json
import re
import threading
import time

import jsonpath
import requests
from pypushdeer import PushDeer

zwyy_times = int(time.time())
zwyy_day = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))

zwyy_json_load = json.load(open('D:\L_Code\zwyy_json.json', 'r', encoding='utf-8'))
zwyy_user = jsonpath.jsonpath(zwyy_json_load, '$..user')[0]
zwyy_time = jsonpath.jsonpath(zwyy_json_load, '$..time')[0]
zwyy_roomId = jsonpath.jsonpath(zwyy_json_load, '$..room')[0]

zwyy_headers = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"}
Url_default = 'https://zwyy.cidp.edu.cn/ClientWeb/xcus/ic2/Default.aspx'

zwyy_con = requests.Session()
push = PushDeer(pushkey=jsonpath.jsonpath(zwyy_json_load, '$..pushkey')[0])


def login(userid, pwd, cookie):
    l_res = 1
    url_login = f"https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/login.aspx?id={userid}&pwd={pwd}&act=login"
    zwyy_login = zwyy_con.get(url_login, data=cookie, headers=zwyy_headers)
    if '个人预约制度' in zwyy_login.text:
        l_res = jsonpath.jsonpath(zwyy_login.json(), '$..name')[0]
    if '输入有误' in zwyy_login.text:
        l_res = 11
    return l_res


def get_room(roomid, cookie):
    url_get_rsv_sta = f"https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/device.aspx?byType=devcls&classkind=8&display=fp&md=d&room_id={roomid}&purpose=&selectOpenAty=&cld_name=default&date={zwyy_day}&fr_start={jsonpath.jsonpath(zwyy_time, '$..start_time')[0]}&fr_end={jsonpath.jsonpath(zwyy_time, '$..end_time')[0]}&act=get_rsv_sta&_={zwyy_times}"
    zwyy_get_room = zwyy_con.get(url_get_rsv_sta, data=cookie, headers=zwyy_headers)
    g_res = jsonpath.jsonpath(zwyy_get_room.json(), '$..devId')
    return g_res


def set_resv(devid, time_n, cookie, name):
    url_set_resv = "https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/reserve.aspx?dialogid=" \
                   "&dev_id={dev}" \
                   "&lab_id=&kind_id=&room_id=&type=dev&prop=&test_id=&term=&number=&classkind=&test_name=" \
                   "&start={day}+{start_time}&end={day}+{end_time}" \
                   "&start_time={start_time_n}&end_time={end_time_n}" \
                   "&up_file=&memo=&act=set_resv&_={timestamp}"

    zwyy_set_resv = zwyy_con.get(
        url_set_resv.format(dev=devid, day=zwyy_day, start_time=jsonpath.jsonpath(zwyy_time, '$..start_time')[time_n],
                            end_time=jsonpath.jsonpath(zwyy_time, '$..end_time')[time_n],
                            start_time_n=re.sub(':', '', jsonpath.jsonpath(zwyy_time, '$..start_time')[time_n]),
                            end_time_n=re.sub(':', '', jsonpath.jsonpath(zwyy_time, '$..end_time')[time_n]),
                            timestamp=zwyy_times), data=cookie, headers=zwyy_headers)
    msg = jsonpath.jsonpath(zwyy_set_resv.json(), '$..msg')
    if '操作成功' in msg[0]:
        push.send_text(
            f"姓名：{name}，预约次日位置：{devid}，成功。时间段为{jsonpath.jsonpath(zwyy_time, '$..start_time')[time_n]}到{jsonpath.jsonpath(zwyy_time, '$..end_time')[time_n]}")
    return msg[0]


def try_set_resv(userid, pwd, room_id, time_no, cookie, name, users):
    dev = get_room(room_id, cookie)
    dev_n = len(dev)
    n = 0
    tr_res = 1
    while n < dev_n:
        priority_res = set_resv((jsonpath.jsonpath(zwyy_user[users], '$..priority'))[users], time_no, cookie, name)
        if '操作成功' in priority_res:
            tr_res = 0
            break
        t_res = set_resv(dev[n], time_no, cookie, name)
        # print(t_res)
        if '未登录' in t_res:
            name = login(userid, pwd, cookie)
            n -= 1
        if '请在7:00之后' in t_res:
            time.sleep(1)
            n -= 1
        if '操作成功' in t_res:
            tr_res = 0
            break
        n += 1
    return tr_res


def run_zwyy(userid, pwd, time_no, users):
    zwyy_con.get(Url_default)
    zwyy_cookie = zwyy_con.cookies.get_dict()

    l_res = login(userid, pwd, zwyy_cookie)
    if l_res == 11:
        pass
    room_no = 0
    t_res = 1
    while room_no < len(zwyy_roomId):
        t_res = try_set_resv(userid, pwd, zwyy_roomId[room_no], time_no, zwyy_cookie, l_res, users)
        room_no += 1
        if t_res == 0:
            break
    if t_res == 1:
        res = f"姓名：{l_res}，日期：{zwyy_day}，{jsonpath.jsonpath(zwyy_time, '$..start_time')[time_no]}至{jsonpath.jsonpath(zwyy_time, '$..end_time')[time_no]}时间段预约座位失败"
        push.send_text(res)
    pass


def zwyy_th(userid, pwd, users):
    time_thread = 0
    while time_thread < len(zwyy_time):
        threading.Thread(target=run_zwyy, args=(userid, pwd, time_thread, users,)).start()
        time_thread += 1
    pass


def main():
    push.send_text(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + ' 开始')
    users = 0
    while users < len(zwyy_user):
        zwyy_th((jsonpath.jsonpath(zwyy_user[users], '$..id'))[0], (jsonpath.jsonpath(zwyy_user[users], '$..pwd'))[0],
                users)
        users += 1
        pass


main()
