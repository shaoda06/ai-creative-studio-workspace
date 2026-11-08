import assert from 'node:assert/strict';
export async function checkCandidateMessages(page, width) {
  const business = page.getByTestId('business');
  const mode = value => business.locator('[aria-label="候选提示测试状态"]').getByRole('button', { name: value, exact: true }).click();
  const panel = business.getByRole('region', { name: '当前候选提示' });
  await business.getByRole('combobox', { name: '画质选择' }).click();
  await page.getByRole('option', { name: '一采', exact: true }).click();
  await business.getByRole('combobox', { name: '版本切换' }).click();
  await page.getByRole('option', { name: /候选一/ }).click();
  await mode('normal');
  assert.equal(await panel.count(), 0);
  await mode('issues');
  const details = panel.locator('details');
  await details.waitFor();
  assert.equal(await details.getAttribute('open'), null);
  for (const wide of [false, true]) {
    const isWide = await business.locator('.segment-workspace').evaluate(el => el.classList.contains('is-wide'));
    if (isWide !== wide) await business.getByRole('button', { name: wide ? '宽屏显示' : '恢复布局', exact: true }).click();
    const bounds = await panel.boundingBox(), selectors = await business.locator('.segment-selectors').boundingBox();
    const layout = await business.locator('.segment-workspace').boundingBox();
    assert.ok(bounds.y >= selectors.y + selectors.height - 1 && bounds.y + bounds.height <= layout.y + 1);
    assert.equal(await business.locator('.segment-script .generation-context-issues').count(), 0);
    await business.getByRole('button', { name: '提示词', exact: true }).click();
    assert.equal(await panel.count(), 1);
    await business.getByRole('button', { name: '分镜脚本', exact: true }).click();
  }
  await details.locator('summary').click();
  assert.ok(await details.getAttribute('open') !== null);
  const select = business.getByRole('combobox', { name: '版本切换' });
  await select.click();
  const current = await details.locator('summary').innerText();
  await page.getByRole('option', { name: current.includes('R001') ? /候选二/ : /候选一/ }).click();
  assert.equal(await panel.locator('details').getAttribute('open'), null);
  await mode('pending');
  await panel.getByText(/这版视频还没生成/).waitFor();
  await mode('error');
  await panel.getByRole('button', { name: '重新读取', exact: true }).click();
  await panel.waitFor({ state: 'detached' });
  console.log(`候选提示：${width}px统一位置、折叠、版本切换、文字标签、普通/宽屏、未生成及失败重试通过。`);
}
