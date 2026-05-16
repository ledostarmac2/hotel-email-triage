Option Explicit

Private Const APP_IMPORT_URL As String = "http://127.0.0.1:8000/api/outlook-desktop/import-json"
Private Const MAILBOX_NAME As String = "NYCWA_Reservations"
Private Const INBOX_NAME As String = "Inbox"
Private Const MAX_BODY_CHARS As Long = 16000

Sub ExportNYCWAReservationsInboxOnly()
    On Error GoTo HandleError

    Dim ns As Outlook.NameSpace
    Dim rootFolder As Outlook.MAPIFolder
    Dim inboxFolder As Outlook.MAPIFolder
    Dim exportPath As String
    Dim json As String

    Set ns = Application.GetNamespace("MAPI")
    Set rootFolder = FindMailboxRoot(ns, MAILBOX_NAME)
    If rootFolder Is Nothing Then Err.Raise vbObjectError + 1, , "Could not find mailbox: " & MAILBOX_NAME

    Set inboxFolder = rootFolder.Folders(INBOX_NAME)
    exportPath = ExportRoot() & CleanFileName(MAILBOX_NAME) & "\" & CleanFileName(INBOX_NAME)
    EnsureNestedFolder ExportBase()
    EnsureNestedFolder ExportRoot()
    EnsureNestedFolder ExportRoot() & CleanFileName(MAILBOX_NAME)
    EnsureNestedFolder exportPath

    json = BuildInboxPayload(inboxFolder, exportPath)
    PostJson APP_IMPORT_URL, json
    Exit Sub

HandleError:
    MsgBox "Outlook refresh failed: " & Err.Description, vbCritical
End Sub

Private Function ExportRoot() As String
    ExportRoot = ExportBase() & "outlook_exports\"
End Function

Private Function ExportBase() As String
    ExportBase = Environ$("USERPROFILE") & "\Documents\ReplyRight\"
End Function

Private Function BuildInboxPayload(folder As Outlook.MAPIFolder, exportPath As String) As String
    Dim item As Object
    Dim mail As Outlook.MailItem
    Dim parts As Collection
    Dim i As Long
    Dim messageJson As String
    Dim subjectPart As String
    Dim filePath As String

    Set parts = New Collection

    For i = 1 To folder.Items.Count
        Set item = folder.Items(i)

        If TypeOf item Is Outlook.MailItem Then
            Set mail = item

            subjectPart = CleanFileName(mail.Subject)
            If Len(subjectPart) = 0 Then subjectPart = "No Subject"

            filePath = exportPath & "\" & _
                Format(mail.ReceivedTime, "yyyy-mm-dd_hh-nn-ss") & "_" & _
                Left(subjectPart, 80) & "_" & CStr(i) & ".msg"

            If Len(Dir(filePath)) = 0 Then
                mail.SaveAs Left(filePath, 245), olMSG
            End If

            messageJson = "{" & _
                JsonPair("graph_message_id", mail.EntryID) & "," & _
                JsonPair("subject", mail.Subject) & "," & _
                JsonPair("sender_name", mail.SenderName) & "," & _
                JsonPair("sender_email", mail.SenderEmailAddress) & "," & _
                JsonPair("from_name", mail.SenderName) & "," & _
                JsonPair("from_email", mail.SenderEmailAddress) & "," & _
                JsonPair("received_datetime", Format(mail.ReceivedTime, "yyyy-mm-dd\Thh:nn:ss")) & "," & _
                JsonPair("body_preview", Left(CleanPreview(mail.Body), 240)) & "," & _
                JsonPair("body_content_type", "text") & "," & _
                JsonPair("body_content", Left(mail.Body, MAX_BODY_CHARS)) & "," & _
                JsonPair("body_text", Left(mail.Body, MAX_BODY_CHARS)) & "," & _
                JsonPair("conversation_id", mail.ConversationID) & "," & _
                JsonPair("importance", ImportanceName(mail.Importance)) & "," & _
                """has_attachments"":" & LCase(CStr(mail.Attachments.Count > 0)) & _
            "}"

            parts.Add messageJson
        End If

        If i Mod 25 = 0 Then DoEvents
    Next i

    BuildInboxPayload = "{" & _
        JsonPair("mailbox", MAILBOX_NAME) & "," & _
        JsonPair("folder", INBOX_NAME) & "," & _
        """messages"":[" & JoinCollection(parts, ",") & "]" & _
    "}"
End Function

Private Sub PostJson(url As String, payload As String)
    Dim http As Object
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "POST", url, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.Send payload

    If http.Status < 200 Or http.Status >= 300 Then
        Err.Raise vbObjectError + 2, , "Local app import failed: HTTP " & http.Status & " " & http.ResponseText
    End If
End Sub

Private Function FindMailboxRoot(ns As Outlook.NameSpace, mailboxName As String) As Outlook.MAPIFolder
    Dim folder As Outlook.MAPIFolder

    For Each folder In ns.Folders
        If LCase(folder.Name) = LCase(mailboxName) Then
            Set FindMailboxRoot = folder
            Exit Function
        End If
    Next folder
End Function

Private Sub EnsureNestedFolder(path As String)
    If Len(Dir(path, vbDirectory)) = 0 Then MkDir path
End Sub

Private Function JsonPair(name As String, value As String) As String
    JsonPair = """" & JsonEscape(name) & """:""" & JsonEscape(value) & """"
End Function

Private Function JsonEscape(value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, """", "\""")
    value = Replace(value, vbCrLf, "\n")
    value = Replace(value, vbCr, "\n")
    value = Replace(value, vbLf, "\n")
    value = Replace(value, vbTab, "\t")
    JsonEscape = value
End Function

Private Function JoinCollection(values As Collection, delimiter As String) As String
    Dim result As String
    Dim i As Long

    For i = 1 To values.Count
        If i > 1 Then result = result & delimiter
        result = result & CStr(values(i))
    Next i

    JoinCollection = result
End Function

Private Function CleanPreview(value As String) As String
    value = Replace(value, vbCrLf, " ")
    value = Replace(value, vbCr, " ")
    value = Replace(value, vbLf, " ")
    value = Replace(value, vbTab, " ")
    CleanPreview = Trim(value)
End Function

Private Function CleanFileName(text As String) As String
    Dim badChars As Variant
    Dim ch As Variant

    badChars = Array("\", "/", ":", "*", "?", """", "<", ">", "|", vbCr, vbLf, vbTab)

    For Each ch In badChars
        text = Replace(text, ch, "_")
    Next ch

    CleanFileName = Trim(text)
End Function

Private Function ImportanceName(value As OlImportance) As String
    If value = olImportanceHigh Then
        ImportanceName = "high"
    ElseIf value = olImportanceLow Then
        ImportanceName = "low"
    Else
        ImportanceName = "normal"
    End If
End Function
