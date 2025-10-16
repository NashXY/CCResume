import atexit
from ProgramInstance import ProgramInstance

class ProgramInstance:
    instance = ProgramInstance()

def main():
    # 程序开始时 BeginPlay
    ProgramInstance.instance.BeginPlay()
    
    # 程序结束时 EndPlay
    atexit.register(ProgramInstance.instance.EndPlay)
    
    input("按回车键退出程序...") 

if __name__ == "__main__":
    main()
