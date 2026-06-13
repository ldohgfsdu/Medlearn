const test = require('node:test')
const assert = require('node:assert/strict')

function calculateNextReview(current, quality, now = new Date('2026-06-10T00:00:00.000Z')) {
  quality = Math.max(0, Math.min(5, quality))
  let { interval, easeFactor, repetitions } = current

  if (quality < 3) {
    repetitions = 0
    interval = 1
  } else {
    repetitions += 1
    if (repetitions === 1) interval = 1
    else if (repetitions === 2) interval = 6
    else interval = Math.round(interval * easeFactor)
  }

  easeFactor = Math.max(
    1.3,
    easeFactor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
  )

  now.setDate(now.getDate() + interval)
  return { interval, easeFactor, repetitions, nextReview: now.toISOString() }
}

function calculateScore(questions, answers) {
  let correctCount = 0
  const wrongQuestions = []
  const popcount = (value) => {
    let count = 0
    while (value > 0) {
      count += value & 1
      value >>>= 1
    }
    return count
  }

  questions.forEach((question, index) => {
    const answer = answers[index]
    if (answer === undefined) {
      wrongQuestions.push(index)
    } else if (question.type === 'single') {
      if (answer === question.answer) correctCount += 1
      else wrongQuestions.push(index)
    } else if (answer === question.answer) {
      correctCount += 1
    } else {
      const correctBits = answer & question.answer
      const incorrectBits = answer & ~question.answer
      if (popcount(question.answer) > 0 && popcount(correctBits) > 0 && incorrectBits === 0) {
        correctCount += 0.5
      }
      wrongQuestions.push(index)
    }
  })

  return { correctCount, wrongQuestions }
}

test('SM-2 advances a successful second review to six days', () => {
  const result = calculateNextReview(
    { interval: 1, easeFactor: 2.5, repetitions: 1 },
    4
  )
  assert.equal(result.interval, 6)
  assert.equal(result.repetitions, 2)
  assert.ok(Number.isFinite(result.easeFactor))
})

test('SM-2 resets failed reviews without producing NaN', () => {
  const result = calculateNextReview(
    { interval: 30, easeFactor: 2.1, repetitions: 5 },
    1
  )
  assert.equal(result.interval, 1)
  assert.equal(result.repetitions, 0)
  assert.ok(Number.isFinite(result.easeFactor))
})

test('multiple-choice partial credit rejects extra incorrect options', () => {
  const questions = [{ type: 'multiple', answer: 0b0101 }]
  assert.deepEqual(calculateScore(questions, { 0: 0b0001 }), {
    correctCount: 0.5,
    wrongQuestions: [0],
  })
  assert.deepEqual(calculateScore(questions, { 0: 0b0011 }), {
    correctCount: 0,
    wrongQuestions: [0],
  })
})
