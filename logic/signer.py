# auto_sign_backend/logic/signer.py

class Signer:
    def __init__(self, client):
        self.client = client

    def sign_course(self, course):
        # 获取签到任务
        task = self.client.get_sign_task(course["id"])
        if not task or task["code"] != 200:
            return False, "任务获取失败"

        task_id = task["data"]["taskId"]

        # 执行签到
        res = self.client.do_sign(task_id)
        if res["code"] == 200:
            return True, "签到成功"
        else:
            return False, res.get("msg", "unknown error")
