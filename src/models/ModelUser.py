from .entities.User import User

class ModelUser():
    
    @classmethod
    def login(self, db, user):
        try:
            conn = db.acquire()
            cursor = conn.cursor()
            cursor.execute("SELECT IDE, USUARIO, CLAVE FROM ADMINISTRADORES WHERE USUARIO = (:0)", (user.usuario,))
            row = cursor.fetchone()
            cursor.close()
            db.release(conn)
            if row != None:
                user = User(row[0], row[1], User.check_password(row[2], user.password))
                return user
            else:
                return None
        except Exception as ex:
            raise Exception(ex)

    @classmethod
    def get_by_id(self, db, id):
        try:
            conn = db.acquire()
            cursor = conn.cursor()
            cursor.execute("SELECT IDE, USUARIO FROM ADMINISTRADORES WHERE IDE = (:0)", (id,))
            row = cursor.fetchone()
            cursor.close()
            db.release(conn)
            if row != None:
                return User(row[0], row[1], None)
            else:
                return None
        except Exception as ex:
            raise Exception(ex)