import sqlite3

class CCSqlite:
    def __init__(self, db_name):
        self.connection = sqlite3.connect(db_name)
        self.cursor = self.connection.cursor()

    #执行SQL语句
    def Execute(self, query, params=()):
        self.cursor.execute(query, params)
        self.connection.commit()

    #获取查询结果
    def FetchAll(self):
        return self.cursor.fetchall()

    #关闭数据库连接
    def Close(self):
        self.connection.close()