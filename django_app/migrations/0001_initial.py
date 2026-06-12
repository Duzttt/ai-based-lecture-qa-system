# Generated migration for Question Suggestion models

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Notebook",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Name of the notebook", max_length=255, unique=True
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, help_text="Description of the notebook"
                    ),
                ),
                (
                    "document_names",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Comma-separated list of document names in this notebook",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SuggestedQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "question_text",
                    models.TextField(help_text="The suggested question text"),
                ),
                (
                    "question_type",
                    models.CharField(
                        choices=[
                            ("concept", "Concept/Definition"),
                            ("method", "Method/Process"),
                            ("comparison", "Comparison"),
                            ("reason", "Reason/Explanation"),
                            ("example", "Example/Application"),
                        ],
                        default="concept",
                        help_text="Type of question (concept, method, comparison, etc.)",
                        max_length=20,
                    ),
                ),
                (
                    "document_names",
                    models.TextField(
                        help_text="Comma-separated list of document names this was generated from"
                    ),
                ),
                (
                    "click_count",
                    models.IntegerField(
                        default=0,
                        help_text="Number of times this suggestion was clicked",
                    ),
                ),
                (
                    "feedback_score",
                    models.FloatField(
                        blank=True,
                        help_text="User feedback score (if collected)",
                        null=True,
                    ),
                ),
                (
                    "generation_metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional metadata about question generation",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, help_text="When this suggestion was created"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, help_text="When this suggestion was last updated"
                    ),
                ),
                (
                    "notebook",
                    models.ForeignKey(
                        blank=True,
                        help_text="Associated notebook (optional)",
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="suggested_questions",
                        to="django_app.notebook",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="suggestedquestion",
            index=models.Index(
                fields=["-created_at"], name="django_app__created_ea3d9f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="suggestedquestion",
            index=models.Index(
                fields=["question_type"], name="django_app__questio_2c8f5e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="suggestedquestion",
            index=models.Index(
                fields=["click_count"], name="django_app__click__c3a3c3_idx"
            ),
        ),
    ]
