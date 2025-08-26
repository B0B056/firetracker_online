import bcrypt

passwords = ["12345", "abc123"]  # substitui pelas tuas passwords

for pwd in passwords:
    hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    print(f"{pwd}  -->  {hashed}")
