from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    parent_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    captcha = forms.CharField(
        label="验证码", max_length=5,
        widget=forms.TextInput(attrs={"placeholder": "输入图片中的字符", "autocomplete": "off"}),
    )

    class Meta:
        model = Comment
        fields = ("name", "body")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "你的昵称", "autocomplete": "name"}),
            "body": forms.Textarea(attrs={"placeholder": "写下你的评论…", "rows": 4}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("评论提交失败")
        return value
