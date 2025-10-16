from Source.CCSqlite.CCSqlite import CCSqlite

class ProgramInstance:
	def BeginPlay(self):
		print("BeginPlay called.")
		db = CCSqlite("Saved/DataBase/example.db")
		db.Execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
		db.Close()

	def EndPlay(self):
		print("EndPlay called.")
