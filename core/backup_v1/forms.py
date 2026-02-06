from django import forms

class UploadFileForm(forms.Form):
    # The name 'file' here must match the name="file" in your HTML input
    file = forms.FileField()