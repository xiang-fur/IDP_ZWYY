#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

import json
import re
import sys
import threading
import time

import jsonpath
import requests

users = 0
if len(sys.argv) > 1:
    users = int(sys.argv[1])

zwyy_times = int(time.time())
zwyy_day = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))

zwyy_json_load = json.load(open('zwyy_json.json', 'r', encoding='utf-8'))  # 使用cron运行请写完整路径
zwyy_user = jsonpath.jsonpath(zwyy_json_load, '$..user')[0]
if users > len(zwyy_user) - 1:
    users = 0
zwyy_time = jsonpath.jsonpath(zwyy_json_load, '$..time')[0]
zwyy_roomid = jsonpath.jsonpath(zwyy_json_load, '$..roomid')
zwyy_devid = jsonpath.jsonpath(zwyy_json_load, '$..devid')
zwyy_devname = jsonpath.jsonpath(zwyy_json_load, '$..devname')
zwyy_pushkey = jsonpath.jsonpath(zwyy_json_load, '$..pushkey')[0]
zwyy_priorityid = (jsonpath.jsonpath(zwyy_user[users], '$..priority_id'))[0]
zwyy_priorityname = (jsonpath.jsonpath(zwyy_user[users], '$..priority_name'))[0]

zwyy_headers = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"}

zwyy_con = requests.Session()


def login(userid, pwd):
    l_res = 1
    url_login = f"https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/login.aspx?id={userid}&pwd={pwd}&act=login"
    zwyy_login = zwyy_con.get(url_login, headers=zwyy_headers)
    if '个人预约制度' in zwyy_login.text:
        l_res = jsonpath.jsonpath(zwyy_login.json(), '$..name')[0]
    if '输入有误' in zwyy_login.text:
        l_res = "Login Error!"
    return l_res


def get_room_info(roomid):
    url_get_rsv_sta = f"https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/device.aspx?byType=devcls&classkind=8&display=fp&md=d&room_id={roomid}&purpose=&selectOpenAty=&cld_name=default&date={zwyy_day}&fr_start={jsonpath.jsonpath(zwyy_time, '$..start_time')[0]}&fr_end={jsonpath.jsonpath(zwyy_time, '$..end_time')[0]}&act=get_rsv_sta&_={zwyy_times}"
    zwyy_get_room = zwyy_con.get(url_get_rsv_sta, headers=zwyy_headers)
    g_res = jsonpath.jsonpath(zwyy_get_room.json(), '$..devname')
    return g_res


def pushdeer(text):
    push_url = f"{jsonpath.jsonpath(zwyy_json_load, '$..push_url')[0]}pushkey={zwyy_pushkey[users]}&text={text}"
    requests.post(push_url)
    pass


def set_resv(devid, devname, time_n, name):
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
                            timestamp=zwyy_times), headers=zwyy_headers)
    msg = jsonpath.jsonpath(zwyy_set_resv.json(), '$..msg')
    if '操作成功' in msg[0]:
        pushdeer(
            f"姓名：{name}，预约次日位置：{devname}，成功。时间段为{jsonpath.jsonpath(zwyy_time, '$..start_time')[time_n]}到{jsonpath.jsonpath(zwyy_time, '$..end_time')[time_n]}")
    return msg[0]


def try_set_resv(userid, pwd, time_no, name, room_no):
    dev_id = zwyy_devid[room_no]
    dev_name = zwyy_devname[room_no]
    n = 0
    tr_res = 1
    used_priority = 0
    while n < len(dev_id):
        if used_priority == 0:
            priority_res = set_resv(zwyy_priorityid, zwyy_priorityname, time_no, name)
            if 'ERRMSG_RESV_CONFLICT' in priority_res:
                used_priority = 1
            if '操作成功' in priority_res:
                tr_res = 0
                break
            if '未登录' in priority_res:
                name = login(userid, pwd)
                continue
            if '请在7:00之后' in priority_res:
                time.sleep(0.5)
                continue
        if dev_id[n] == zwyy_priorityid:
            n += 1
        t_res = set_resv(dev_id[n], dev_name[n], time_no, name)
        if '未登录' in t_res:
            name = login(userid, pwd)
            continue
        if '操作成功' in t_res:
            tr_res = 0
            break
        n += 1
    return tr_res


def run_zwyy(userid, pwd, time_no):
    l_res = login(userid, pwd)
    if l_res == 1 or l_res == "Login Error!":
        pushdeer(f"学号：{userid}，登录失败")
        sys.exit(1)
    room_no = 0
    t_res = 1
    while room_no < len(zwyy_roomid):
        t_res = try_set_resv(userid, pwd, time_no, l_res, room_no)
        room_no += 1
        if t_res == 0:
            break
    if t_res == 1:
        res = f"姓名：{l_res}，日期：{zwyy_day}，{jsonpath.jsonpath(zwyy_time, '$..start_time')[time_no]}至{jsonpath.jsonpath(zwyy_time, '$..end_time')[time_no]}时间段预约座位失败 "
        pushdeer(res)
    pass


def zwyy_th(userid, pwd):
    time_thread = 0
    while time_thread < len(zwyy_time):
        threading.Thread(target=run_zwyy, args=(userid, pwd, time_thread,)).start()
        time_thread += 1
    pass


def main():
    pushdeer(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + ' 开始')
    zwyy_th((jsonpath.jsonpath(zwyy_user[users], '$..id'))[0], (jsonpath.jsonpath(zwyy_user[users], '$..pwd'))[0])
    pass


main()
