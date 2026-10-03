// Слой 3, тот же набор в Jenkins. Смысл не в том, что Jenkins нужен, а в том,
// что набор не привязан к одной системе CI.
//
// Требования к агенту: docker, containerlab, python3-venv. Allure-отчёт
// рисует плагин Allure; нет плагина — остаются сырые результаты артефактом.
pipeline {
  agent any

  parameters {
    choice(name: 'BENCH', choices: ['virtual-l3', 'virtual-dc', 'virtual-cpe'],
           description: 'какой стенд поднимать')
  }

  environment {
    // Топология выводится из имени стенда: держать это соответствие в двух
    // местах значит однажды развести.
    TOPO = """${[
      'virtual-l3' : 'l3-switches',
      'virtual-dc' : 'dc-fabric',
      'virtual-cpe': 'cpe-sdwan',
    ][params.BENCH]}"""
    VENV = "${WORKSPACE}/.venv"
  }

  options {
    timeout(time: 40, unit: 'MINUTES')
    disableConcurrentBuilds()
  }

  stages {
    stage('Окружение') {
      steps {
        // Своё окружение, а не системный python: на агенте он чужой и может
        // быть защищён от записи (PEP 668).
        sh '''
          python3 -m venv "$VENV"
          "$VENV/bin/python" -m pip install --upgrade pip
          "$VENV/bin/python" -m pip install -e '.[test]' ruff
        '''
      }
    }

    stage('Каркас') {
      steps {
        sh '''
          "$VENV/bin/ruff" check .
          "$VENV/bin/pytest" tests --no-header
        '''
      }
    }

    stage('Стенд') {
      steps {
        sh 'make -C lab image'
        sh 'make -C lab up TOPO="$TOPO"'
      }
    }

    stage('Тесты') {
      steps {
        sh '"$VENV/bin/pytest" --bench "$BENCH" --require-bench'
      }
    }
  }

  post {
    always {
      sh 'make -C lab down TOPO="$TOPO" || true'
      archiveArtifacts artifacts: 'allure-results/**', allowEmptyArchive: true
      script {
        // Плагина может не быть — прогон из-за этого падать не должен.
        try {
          allure includeProperties: false, results: [[path: 'allure-results']]
        } catch (err) {
          echo "Allure не собран: ${err}. Сырые результаты лежат в артефактах."
        }
      }
    }
    cleanup {
      sh 'rm -rf "$VENV"'
    }
  }
}
