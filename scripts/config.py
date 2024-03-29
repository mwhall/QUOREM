import sys
def main():
	db_name = sys.argv[1]
	uname = sys.argv[2]
	pswd = sys.argv[3]
	cwd = sys.argv[4]
	with open('{0}/quorem/settings.py'.format(cwd), 'r') as file:
		filedata = file.readlines()

		index = 0
		new_data = ""
		for line in filedata:
			if line[:7] == "DATABAS":
				filedata[index + 3] = "        'NAME': '{0}',\n".format(db_name)
				filedata[index + 4] = "        'USER': '{0}',\n".format(uname)
				filedata[index + 5] = "        'PASSWORD': '{0}',\n".format(pswd)
			new_data += line
			index += 1

	with open('{0}/quorem/settings.py'.format(cwd), 'w') as file:
		file.write(new_data)

if __name__ == '__main__':
	main()
