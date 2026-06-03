# 导入 MySQL 连接库
import pymysql
import pymysql.err
# 导入pandas
import pandas as pd
# 导入配置和日志
from base import Config, logger


class MySQLClient:
    def __init__(self):
        self.logger = logger
        self._config = {
            "host": Config().MYSQL_HOST,
            "port": Config().MYSQL_PORT,
            "user": Config().MYSQL_USER,
            "password": Config().MYSQL_PASSWORD,
            "database": Config().MYSQL_DATABASE,
            "charset": "utf8mb4",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "autocommit": True,
        }
        self._connect()

    def _connect(self):
        try:
            self.connection = pymysql.connect(**self._config)
            self.cursor = self.connection.cursor()
            self.logger.info("MySQL 连接成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"MySQL 连接失败: {e}")
            raise

    def _ensure_connection(self):
        try:
            self.connection.ping(reconnect=True)
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
            self.logger.warning(f"MySQL 连接断开，正在重连: {e}")
            self._connect()

    def create_table(self):
        self._ensure_connection()
        create_table_query = '''
                             CREATE TABLE IF NOT EXISTS faq_kb
                             (
                                 id
                                 INT
                                 AUTO_INCREMENT
                                 PRIMARY
                                 KEY,
                                 product_line
                                 VARCHAR
                             (
                                 50
                             ),
                                 question VARCHAR
                             (
                                 1000
                             ),
                                 answer VARCHAR
                             (
                                 1000
                             )
                                 ) \
                             '''
        try:
            self.cursor.execute(create_table_query)
            self.connection.commit()
            self.logger.info("表创建成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"表创建失败: {e}")
            raise

    def insert_data(self, csv_path):
        try:
            data = pd.read_csv(csv_path)
            # 数据单条写入
            for _, row in data.iterrows():
                insert_query = "INSERT INTO faq_kb (product_line, question, answer) VALUES (%s, %s, %s)"
                self.cursor.execute(insert_query, (row['product_line'], row['问题'], row['答案']))
            self.connection.commit()
            self.logger.info("数据插入成功")
        except Exception as e:
            self.logger.error(f"数据插入失败: {e}")
            self.connection.rollback()  # 数据的回滚
            raise

    def fetch_questions(self):
        self._ensure_connection()
        try:
            # 执行查询
            self.cursor.execute("SELECT question FROM faq_kb")
            # 获取结果
            results = self.cursor.fetchall()
            # 记录获取成功
            self.logger.info("成功获取问题")
            # 返回结果
            return results
        except pymysql.MySQLError as e:
            # 记录查询失败
            self.logger.error(f"查询失败: {e}")
            # 返回空列表
            return []

    def fetch_answer(self, question):
        self._ensure_connection()
        try:
            # 执行查询
            self.cursor.execute("SELECT answer FROM faq_kb WHERE question=%s", (question,))
            # 获取结果
            result = self.cursor.fetchone()
            # 返回答案或 None
            return result[0] if result else None
        except pymysql.MySQLError as e:
            # 记录答案获取失败
            self.logger.error(f"答案获取失败: {e}")
            # 返回 None
            return None

    def close(self):
        try:
            self.cursor.close()
            self.connection.close()
            self.logger.info("MySQL 连接已关闭")
        except pymysql.MySQLError as e:
            # 记录关闭失败
            self.logger.error(f"关闭连接失败: {e}")


if __name__ == '__main__':
    mysql_client = MySQLClient()
    mysql_client.create_table()
    mysql_client.insert_data('../data/faq_data.csv')
