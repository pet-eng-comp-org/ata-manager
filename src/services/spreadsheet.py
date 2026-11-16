from googleapiclient.errors import HttpError
import schedule

# O processo fica dias ocioso entre reunioes e a conexao HTTPS com o Google
# cai nesse meio-tempo. Com retentativas, a biblioteca reabre a conexao em vez
# de estourar BrokenPipeError / ConnectionResetError.
NUM_RETRIES = 3

class Spreadsheet:
  # ===============================================
  def __init__(self, service, spreadsheet_id, range):
    self.service = service
    self.range = range
    self.spreadsheetId = spreadsheet_id
    self.content = self.__get_content(self.spreadsheetId, self.range)

  # ===============================================
  def __get_content(self, spreadsheet_id, range):
    values = []
    try:
      content = self.service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range).execute(num_retries=NUM_RETRIES)
      values = content.get('values', [])
    except HttpError as error:
      print(error)
    return values  

  # ===============================================
  def __update_status(self, index, column):
    range = f"{column}{index+2}"
    value = [[1]]
    try:
      self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheetId, 
      range=range, valueInputOption="USER_ENTERED", body={'values': value}).execute(num_retries=NUM_RETRIES)
      print('Status updated successfully!')
    except HttpError as error:
      print(error)

  # ===============================================
  def __reset_status(self, column):
    last_row = len(self.content)
    if last_row < 2:
      return
    array = [[0] for _ in range(last_row - 1)]
    try:
      self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheetId, 
      range=f"{column}2:{column}{last_row}", valueInputOption="USER_ENTERED", body={'values': array}).execute(num_retries=NUM_RETRIES)
      print('Status reseted sucefully!')
    except HttpError as error:
      print(error)

  # ===============================================
  #Retorna todos os emails
  def get_students(self):
    students = []
    content = self.content
    for person in content:
      students.append({'name': person[0],'email':person[2]})

    students.pop(0)
    return students

  # ===============================================
  #Retorna o horário da reunião
  def get_time(self):
    content = self.content
    time = content[1][4].split(":")
    hour = int(time[0])
    # hour -= 2 #Este parametro pode ser modificavel dependendo da regiao
    return f"{hour}:{time[1]}"

  # ===============================================
  def schedule_job(self, main):
    content = self.content
    day = content[1][5]
    print(f"Day: {day}")
    if(day == 'segunda-feira'):
      schedule.every().monday.at(self.get_time()).do(main)
    elif(day == 'terça-feira'):
      schedule.every().tuesday.at(self.get_time()).do(main)
    elif(day == 'quarta-feira'):
      schedule.every().wednesday.at(self.get_time()).do(main)
    elif(day == 'quinta-feira'):
      schedule.every().thursday.at(self.get_time()).do(main)
    elif(day == 'sexta-feira'):
      schedule.every().friday.at(self.get_time()).do(main)
    elif (day == "sábado"):
      schedule.every().saturday.at(self.get_time()).do(main)
    elif (day == "domingo"):
      schedule.every().sunday.at(self.get_time()).do(main)

  # ===============================================
  # Le a planilha de novo. O processo fica no ar por semanas, e sem isto cada
  # execucao semanal usava o conteudo lido na subida, com os status velhos.
  def refresh(self):
    self.content = self.__get_content(self.spreadsheetId, self.range)

  # ===============================================
  # Linha incompleta (celula vazia no fim) vem mais curta da API do Sheets.
  @staticmethod
  def __campo(linha, i):
    return linha[i] if len(linha) > i else ""

  @staticmethod
  def __numero(valor):
    try:
      return int(valor)
    except (TypeError, ValueError):
      return 0

  # ===============================================
  # Presentes: linhas com nome (coluna A) e presenca (coluna D) diferente de 0.
  def __presentes(self):
    return [
      (i, pessoa)
      for i, pessoa in enumerate(self.content[1:])
      if self.__campo(pessoa, 0).strip()
      and self.__numero(self.__campo(pessoa, 3)) != 0
    ]

  # ===============================================
  # Seleciona, entre os candidatos, o primeiro com status 0 para o cargo. Se
  # todos ja estiverem com status 1, reinicia a rodada desse cargo.
  def __get_todays_responsible(self, candidatos, status_index, status_column):
    responsavel = next(
      (
        (i, pessoa)
        for i, pessoa in candidatos
        if self.__numero(self.__campo(pessoa, status_index)) == 0
      ),
      None,
    )
    if responsavel is None:
      self.__reset_status(status_column)
      responsavel = candidatos[0]

    index, pessoa = responsavel
    self.__update_status(index, status_column)
    return index, self.__campo(pessoa, 0).strip()

  # ===============================================
  # Devolve (writer, condutor), sempre pessoas diferentes. Writer usa a coluna
  # B e condutor a coluna G, cada um com sua propria rodada. Com menos de dois
  # presentes devolve (None, None) e nao marca nenhum status.
  def get_todays_responsibles(self):
    presentes = self.__presentes()
    if len(presentes) < 2:
      return None, None

    writer_index, writer = self.__get_todays_responsible(presentes, 1, "B")
    candidatos = [(i, pessoa) for i, pessoa in presentes if i != writer_index]
    _, conductor = self.__get_todays_responsible(candidatos, 6, "G")
    return writer, conductor
