pipeline {
  agent any
  environment {
    py = "py"   // adjust to "python" if needed
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Install deps') {
      steps {
        bat "${env.py} -m pip install -q -r requirements.txt"
      }
    }

    stage('Prepare reports') {
      steps {
        bat """
          if exist reports rd /s /q reports
          mkdir reports
          xcopy /E /I /Y sample_reports\\* reports\\
          dir reports
        """
      }
    }

    stage('Run parser') {
      steps {
        bat """
          ${env.py} scripts\\parse_cucumber_reports.py -i reports -o report_summary.json
          type summary.md
        """
      }
      post {
        always {
          archiveArtifacts artifacts: 'report_summary.json, summary.md', fingerprint: true
        }
      }
    }

    stage('Generate Dashboard') {
      steps {
        bat """
          if exist results rd /s /q results
          mkdir results
          ${env.py} scripts\\dashboard_generator.py report_summary.json results\\dashboard.html
          dir results
        """
      }
      post {
        always {
          archiveArtifacts artifacts: 'results/dashboard.html', fingerprint: true
        }
      }
    }

    stage('Send summary (email)') {
      when {
        expression { env.SEND_EMAIL == 'true' }
      }
      steps {
        script {
          def summaryText = readFile('summary.md')
          emailext (
            subject: "POC QA Summary - Build ${env.BUILD_NUMBER}",
            body: """<pre>${summaryText}</pre>""",
            to: "${params.EMAIL_TO ?: 'client@example.com'}"
          )
        }
      }
    }
  }
}
